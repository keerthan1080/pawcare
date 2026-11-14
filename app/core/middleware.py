import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import correlation_id_ctx


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates X-Correlation-ID / X-Request-ID on every request."""

    HEADER_NAME = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        cid = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        token = correlation_id_ctx.set(cid)
        try:
            response: Response = await call_next(request)
            response.headers[self.HEADER_NAME] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)
