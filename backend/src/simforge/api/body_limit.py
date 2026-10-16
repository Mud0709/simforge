"""Reject request bodies larger than a fixed limit, before the application reads them.

Without this, FastAPI would read a body of any size into memory before validating it. The
limit applies to every route; the largest legitimate body is a dataset upload (see
``simforge.quant.profiling.limits``), and every other request is under a kilobyte.

Two layers: a declared ``Content-Length`` above the limit is refused at once; a body sent
without one (chunked) is counted as it arrives and cut off at the limit.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await self._reject(send)
                return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    # Stop delivering the body; the app sees a disconnected client.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded and not response_started:
                return  # drop the app's own error response; ours is sent below
            response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await self._reject(send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {"detail": f"The request is larger than the {self.max_bytes:,}-byte limit."}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
