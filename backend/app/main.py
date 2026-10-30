import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .api import auth
from .config import settings

app = FastAPI(title="Vaultly API", version="0.1.0")


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    paths = {
        "/api/v1/auth/login": (5, 60),
        "/api/v1/auth/register": (5, 60),
        "/api/v1/auth/forgot-password": (5, 60),
        "/api/v1/auth/reset-password": (10, 60),
    }

    def __init__(self, app):
        super().__init__(app)
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    async def dispatch(self, request, call_next):
        limit_config = self.paths.get(request.url.path)
        if limit_config and request.method == "POST":
            limit, window = limit_config
            key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
            now = time.monotonic()
            with self.lock:
                timestamps = self.events[key]
                while timestamps and now - timestamps[0] >= window:
                    timestamps.popleft()
                if len(timestamps) >= limit:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many attempts. Please wait and try again."},
                        headers={"Retry-After": str(window)},
                    )
                timestamps.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
