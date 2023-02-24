## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2023 Seecr (Seek You Too B.V.) https://seecr.nl
#
# This file is part of "Metastreams Html"
#
# "Metastreams Html" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Metastreams Html" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Metastreams Html"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

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
