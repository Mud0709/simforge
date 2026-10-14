"""Exception handlers that keep every error response valid, strict JSON."""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors}
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
