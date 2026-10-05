import sys
sys.path.insert(0, '.')
from api.middleware.ratelimit import RateLimitMiddleware, RateLimitConfig
from fastapi import Request
from starlette.datastructures import Headers
import asyncio

class MockRequest:
    def __init__(self, path="/", client_ip="127.0.0.1", user=None):
        self._path = path
        self._client_ip = client_ip
        self.state = type('State', (), {'user': user})()
        self.client = type('Client', (), {'host': client_ip})()
        self.headers = Headers({})
        self.url = type('URL', (), {'path': path})()
    
    @property
    def url(self):
        class URLMock:
            def __init__(self, p):
                self.path = p
        return URLMock(self._path)
    
    @url.setter
    def url(self, value):
        pass

class MockResponse:
    def __init__(self):
        self.headers = {}
        self.status_code = 200

async def call_next(request):
    return MockResponse()

async def test_middleware():
    middleware = RateLimitMiddleware(app=None, config=RateLimitConfig(requests_per_window=2, window_seconds=1))
    # Test anonymous
    req1 = MockRequest(path="/test", client_ip="1.2.3.4")
    resp1 = await middleware.dispatch(req1, call_next)
    assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}"
    req2 = MockRequest(path="/test", client_ip="1.2.3.4")
    resp2 = await middleware.dispatch(req2, call_next)
    assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}"
    req3 = MockRequest(path="/test", client_ip="1.2.3.4")
    resp3 = await middleware.dispatch(req3, call_next)
    assert resp3.status_code == 429, f"Expected 429, got {resp3.status_code}"
    # Test authenticated
    req4 = MockRequest(path="/test", client_ip="5.6.7.8", user={"id": "user123"})
    resp4 = await middleware.dispatch(req4, call_next)
    assert resp4.status_code == 200, f"Expected 200, got {resp4.status_code}"
    req5 = MockRequest(path="/test", client_ip="5.6.7.8", user={"id": "user123"})
    resp5 = await middleware.dispatch(req5, call_next)
    assert resp5.status_code == 200, f"Expected 200, got {resp5.status_code}"
    req6 = MockRequest(path="/test", client_ip="5.6.7.8", user={"id": "user123"})
    resp6 = await middleware.dispatch(req6, call_next)
    assert resp6.status_code == 429, f"Expected 429, got {resp6.status_code}"
    # Ensure separate counters
    req7 = MockRequest(path="/test", client_ip="1.2.3.4")  # anonymous again
    resp7 = await middleware.dispatch(req7, call_next)
    assert resp7.status_code == 429, f"Expected 429 for anonymous after 2, got {resp7.status_code}"
    print("All tests passed")

if __name__ == "__main__":
    asyncio.run(test_middleware())
