
class Cookie:
    def __init__(self, name):
        self._name = name

    def read_from_request(self, request):
        return request.cookies.get(self._name)

    def write_to_response(self, response, value):
        response.set_cookie(self._name, value)

import autotest
test = autotest.get_tester(__name__)

from aiohttp import web as aiohttp_web

class MockRequest:
    def __init__(self):
        self.cookies = {}

@test
async def test_read_cookie():
    cookie = Cookie(name="koekje")
    request = MockRequest()

    test.eq(None, cookie.read_from_request(request))
    request.cookies['koekje'] = "something"
    test.eq("something", cookie.read_from_request(request))

@test
async def test_write_cookie():
    cookie = Cookie(name="koekje")
    response = aiohttp_web.StreamResponse()

    cookie.write_to_response(response, "The Value")
    test.eq('Set-Cookie: koekje="The Value"; Path=/', str(response.cookies))
