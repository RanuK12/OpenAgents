from starlette.testclient import TestClient
from starlette.requests import Request
from api.middleware.ratelimit import RateLimitMiddleware

class MockUser:
    def __init__(self, is_authenticated=False, is_premium=False):
        self.is_authenticated = is_authenticated
        self.is_premium = is_premium

def test_rate_limit_anonymous_user():
    middleware = RateLimitMiddleware(None)
    request = Request(scope={"type": "http", "method": "GET", "path": "/test", "user": None, "state": {}})
    
    limit = middleware.get_rate_limit(request)
    assert limit == 60

def test_rate_limit_authenticated_user():
    middleware = RateLimitMiddleware(None)
    request = Request(scope={"type": "http", "method": "GET", "path": "/test", "user": MockUser(is_authenticated=True), "state": {}})
    
    limit = middleware.get_rate_limit(request)
    assert limit == 300

def test_rate_limit_premium_user():
    middleware = RateLimitMiddleware(None)
    request = Request(scope={"type": "http", "method": "GET", "path": "/test", "user": MockUser(is_authenticated=True, is_premium=True), "state": {}})
    
    limit = middleware.get_rate_limit(request)
    assert limit == 1000