"""Exception handlers that keep every error response valid, strict JSON."""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MAX_ECHO_CHARS = 200


def _shorten(value: Any) -> Any:
    """Replace file content and long strings in an echo with a note: an upload rejected by
    validation would otherwise be sent back, in full."""
    if isinstance(value, str) and len(value) > MAX_ECHO_CHARS:
        return f"<omitted: {len(value):,} characters>"
    if isinstance(value, dict):
        return {
            k: "<omitted: file content>" if k == "content_base64" else _shorten(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_shorten(v) for v in value]
    return value


def _finite_only(value: Any) -> Any:
    """Replace non-finite floats with their string form.

    FastAPI's default 422 response echoes the rejected input. If that input was ``NaN``
    or ``Infinity`` (which Python's JSON parser accepts), echoing it back makes the
    response itself un-encodable and the client receives a 500 instead of a 422.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _finite_only(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite_only(v) for v in value]
    return value


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = _finite_only(jsonable_encoder(exc.errors()))
    for error in errors:  # only the echoed request parts; our own messages stay whole
        if "input" in error:
            error["input"] = _shorten(error["input"])
        if "loc" in error:
            error["loc"] = _shorten(error["loc"])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors}
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
