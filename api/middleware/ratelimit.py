"""Rate limiting middleware for the OpenAgents API.
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Tuple, Optional


class RateLimitConfig:
    def __init__(
        self,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        burst_limit: int = 20,
        config_auth: Optional['RateLimitConfig'] = None,
        config_anon: Optional['RateLimitConfig'] = None,
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit
        if config_auth is None:
            # create a default config without recursion
            self.config_auth = RateLimitConfig.__new__(RateLimitConfig)
            self.config_auth.requests_per_window = requests_per_window
            self.config_auth.window_seconds = window_seconds
            self.config_auth.burst_limit = burst_limit
            self.config_auth.config_auth = None
            self.config_auth.config_anon = None
        else:
            self.config_auth = config_auth
        if config_anon is None:
            self.config_anon = RateLimitConfig.__new__(RateLimitConfig)
            self.config_anon.requests_per_window = requests_per_window
            self.config_anon.window_seconds = window_seconds
            self.config_anon.burst_limit = burst_limit
            self.config_anon.config_auth = None
            self.config_anon.config_anon = None
        else:
            self.config_anon = config_anon


_request_counts: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))
_auth_request_counts: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_client_key(self, request: Request) -> str:
        user = getattr(request.state, 'user', None)
        if user:
            return f"auth:{request.client.host}"
        return self._get_client_ip(request)

    def _is_rate_limited(self, client_key: str, config: RateLimitConfig) -> Tuple[bool, int]:
        global _request_counts, _auth_request_counts
        if "auth:" in client_key:
            count, window_start = _auth_request_counts[client_key]
        else:
            count, window_start = _request_counts[client_key]
        now = time.time()

        if now - window_start >= config.window_seconds:
            if "auth:" in client_key:
                _auth_request_counts[client_key] = (1, now)
            else:
                _request_counts[client_key] = (1, now)
            return False, config.requests_per_window - 1

        if count >= config.requests_per_window:
            retry_after = int(config.window_seconds - (now - window_start))
            return True, retry_after

        if "auth:" in client_key:
            _auth_request_counts[client_key] = (count + 1, window_start)
        else:
            _request_counts[client_key] = (count + 1, window_start)
        remaining = config.requests_per_window - count - 1
        return False, remaining

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)

        client_key = self._get_client_key(request)
        config = self.config.config_auth if "auth:" in client_key else self.config.config_anon
        is_limited, value = self._is_rate_limited(client_key, config)

        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": value,
                },
                headers={"Retry-After": str(value)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(value)
        response.headers["X-RateLimit-Limit"] = str(self.config.requests_per_window)
        response.headers["X-RateLimit-Auth"] = "true" if "auth:" in client_key else "false"
        return response


def create_rate_limiter(
    requests_per_minute: int = 100,
    burst: int = 20,
    config_auth: Optional[Dict] = None,
    config_anon: Optional[Dict] = None,
) -> RateLimitMiddleware:
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_seconds=60,
        burst_limit=burst,
        config_auth=config_auth,
        config_anon=config_anon,
    )
    return RateLimitMiddleware(app=None, config=config)
