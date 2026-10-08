import time
from fastapi import FastAPI
from starlette.testclient import TestClient
import jwt

# Import our middleware
from api.middleware.ratelimit import RateLimitMiddleware, RateLimitConfig

app = FastAPI()

# Add middleware properly - pass class and kwargs
app.add_middleware(
    RateLimitMiddleware,
    config=RateLimitConfig(),
    jwt_secret='testsecret'
)

# Simple endpoint
@app.get("/test")
def test_endpoint():
    return {"msg": "ok"}

client = TestClient(app)

def test_anonymous():
    print("Testing anonymous tier...")
    headers = {}
    response = client.get("/test", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert int(response.headers["X-RateLimit-Remaining"]) == 59
    print("Anonymous tier verified")

def test_authenticated():
    print("\nTesting authenticated tier...")
    token = jwt.encode({"roles": ["user"]}, "testsecret", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "300"
    print("Authenticated tier verified")

def test_premium():
    print("\nTesting premium tier...")
    token = jwt.encode({"roles": ["premium", "user"]}, "testsecret", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "1000"
    print("Premium tier verified")

if __name__ == "__main__":
    test_anonymous()
    test_authenticated()
    test_premium()
    print("\nAll tests passed!")
