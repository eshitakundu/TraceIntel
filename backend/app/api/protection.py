import hmac

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import Settings


def trusted_proxy(request: Request, settings: Settings) -> bool:
    expected = settings.proxy_token.get_secret_value()
    received = request.headers.get("x-traceintel-proxy-token", "")
    return bool(expected) and hmac.compare_digest(expected.encode(), received.encode())


class RequestProtection(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST" and request.url.path == "/api/v1/analyses":
            settings: Settings = request.app.state.settings
            if settings.environment == "production" and not trusted_proxy(request, settings):
                return JSONResponse(
                    {"detail": "Use the public TraceIntel API origin."}, status_code=403
                )
            try:
                length = int(request.headers.get("content-length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > 4096:
                return JSONResponse(
                    {"detail": "A JSON body of at most 4096 bytes is required."}, status_code=413
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
