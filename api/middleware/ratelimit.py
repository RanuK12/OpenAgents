# Contributor: dev-bounties
# Platform Initialization: Ranukita autonomous agent — bounty hunter mode
# Runtime Environment: macOS 15.6 (Darwin 24.6.0), arm64, /tmp/OpenAgents, zsh 5.9

"""Rate limiting middleware for the OpenAgents API with three-tier limits."""

import time
import jwt
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Tuple, Optional


class RateLimitConfig:
    def __init__(
        self,
        requests_per_window: int = 60,
        window_seconds: int = 60,
        burst_limit: int = 20,
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit


# In-memory store — counters reset when server restarts
# Key format: "ip:tier" where tier is "anonymous", "authenticated", or "premium"
_request_counts: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))

# Tier limits (requests per minute)
TIER_LIMITS = {
    "anonymous": 60,
    "authenticated": 300,
    "premium": 1000,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: RateLimitConfig = None, jwt_secret: str = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.jwt_secret = jwt_secret or "changeme"

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_tier_from_request(self, request: Request) -> str:
        """Determine rate limit tier from request auth state."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return "anonymous"

        token = auth_header[7:]  # Remove "Bearer " prefix
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            roles = payload.get("roles", [])
            if "premium" in roles:
                return "premium"
            return "authenticated"
        except jwt.InvalidTokenError:
            return "anonymous"

    def _get_limit_for_tier(self, tier: str) -> int:
        return TIER_LIMITS.get(tier, TIER_LIMITS["anonymous"])

    def _get_storage_key(self, client_ip: str, tier: str) -> str:
        return f"{client_ip}:{tier}"

    def _is_rate_limited(self, storage_key: str, limit: int) -> Tuple[bool, int, int]:
        global _request_counts
        count, window_start = _request_counts[storage_key]
        now = time.time()

        # Fixed window rate limiting
        if now - window_start >= self.config.window_seconds:
            _request_counts[storage_key] = (1, now)
            return False, limit - 1, int(self.config.window_seconds)

        if count >= limit:
            retry_after = int(self.config.window_seconds - (now - window_start))
            return True, 0, retry_after

        _request_counts[storage_key] = (count + 1, window_start)
        remaining = limit - count - 1
        reset_time = int(window_start + self.config.window_seconds)
        return False, remaining, reset_time

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        tier = self._get_tier_from_request(request)
        limit = self._get_limit_for_tier(tier)
        storage_key = self._get_storage_key(client_ip, tier)

        is_limited, remaining, reset_or_retry = self._is_rate_limited(storage_key, limit)

        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": reset_or_retry,
                },
                headers={
                    "Retry-After": str(reset_or_retry),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + reset_or_retry),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_or_retry)
        return response


def create_rate_limiter(
    requests_per_minute: int = 60,
    burst: int = 20,
    jwt_secret: str = None,
) -> RateLimitMiddleware:
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_seconds=60,
        burst_limit=burst,
    )
    return RateLimitMiddleware(app=None, config=config, jwt_secret=jwt_secret)