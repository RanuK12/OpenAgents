import time
from fastapi import FastAPI
from starlette.testclient import TestClient
import jwt

from api.middleware.ratelimit import RateLimitMiddleware, RateLimitConfig

app = FastAPI()

app.add_middleware(
    RateLimitMiddleware,
    config=RateLimitConfig(),
    jwt_secret='testsecret'
)

@app.get("/test")
def test_endpoint():
    return {"msg": "ok"}

client = TestClient(app)

def test_anonymous_limit_exceeded():
    print("Testing anonymous tier limit exceeded...")
    headers = {}
    for i in range(65):
        response = client.get("/test", headers=headers)
        if i < 60:
            assert response.status_code == 200
            print(f"Request {i+1}: {response.status_code}, Remaining: {response.headers.get('X-RateLimit-Remaining')}")
        else:
            print(f"Request {i+1}: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            assert response.status_code == 429
            assert response.headers["X-RateLimit-Limit"] == "60"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            assert "Retry-After" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            print("429 with Retry-After verified!")
            break

if __name__ == "__main__":
    test_anonymous_limit_exceeded()
    print("\n429 test passed!")
