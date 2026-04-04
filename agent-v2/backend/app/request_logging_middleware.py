"""HTTP request logging with optional X-Request-ID propagation."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

log = logging.getLogger("app.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        hdr = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        rid = (hdr or "").strip() or str(uuid.uuid4())
        token = request_id_ctx.set(rid)
        t0 = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                dt = time.perf_counter() - t0
                log.exception(
                    "request failed method=%s path=%s request_id=%s duration_s=%.4f",
                    request.method,
                    request.url.path,
                    rid,
                    dt,
                )
                raise
            dt = time.perf_counter() - t0
            response.headers["X-Request-ID"] = rid
            log.info(
                "request method=%s path=%s status=%s duration_s=%.4f request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                dt,
                rid,
            )
            return response
        finally:
            request_id_ctx.reset(token)
