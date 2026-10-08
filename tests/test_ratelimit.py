"""Test cases for the rate limiting middleware."""

import pytest
import time
import jwt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from api.middleware.ratelimit import RateLimitMiddleware, RateLimitConfig, TIER_LIMITS


# Mock JWT secret
JWT_SECRET = "changeme"


# Create a FastAPI app with the rate limiting middleware
app = FastAPI()

# Add the rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    config=RateLimitConfig(),  # Usa la configuración por defecto
    jwt_secret=JWT_SECRET,
)


# Test endpoint
@app.get("/test")
def test_endpoint(request: Request):
    return {"message": "Test endpoint"}


# Test client
client = TestClient(app)


def create_test_token(role: str = "user") -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "roles": [role],
        "sub": "123",
        "exp": int(time.time()) + 3600  # Expire in 1 hour
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def test_rate_limit_anonymous():
    response = client.get("/test")
    assert response.status_code == 200
    assert int(response.headers.get("X-RateLimit-Limit")) == TIER_LIMITS["anonymous"]
    assert int(response.headers.get("X-RateLimit-Remaining")) == TIER_LIMITS["anonymous"] - 1


def test_rate_limit_authenticated():
    token = create_test_token("user")
    response = client.get("/test", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert int(response.headers.get("X-RateLimit-Limit")) == TIER_LIMITS["authenticated"]


def test_rate_limit_premium():
    token = create_test_token("premium")
    response = client.get("/test", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert int(response.headers.get("X-RateLimit-Limit")) == TIER_LIMITS["premium"]


def test_rate_limit_exceeded_anonymous():
    from api.middleware.ratelimit import _request_counts
    _request_counts.clear()
    
    # Hacer exactamente el límite de solicitudes para anónimo
    for _ in range(TIER_LIMITS["anonymous"]):
        response = client.get("/test")
        assert response.status_code == 200
    
    # La siguiente solicitud debería ser rechazada
    response = client.get("/test")
    assert response.status_code == 429
    assert "Rate limit exceeded" in str(response.json())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])