## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2022 Seecr (Seek You Too B.V.) https://seecr.nl
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

from metastreams.html import DynamicHtml
from aiohttp import web as aiohttp_web
import traceback

def dynamic_handler(dHtml):
    async def _handler(request):
        response = aiohttp_web.StreamResponse(
            status=200,
            reason='OK',
        )

        try:
            for each in dHtml.handle_request(request=request, response=response):
                if not response.prepared:
                    if not 'Content-Type' in response.headers:
                        response.headers['Content-Type'] = 'text/html; charset=utf-8'
                    await response.prepare(request)
                await response.write(bytes(each, encoding="utf-8"))
        except aiohttp_web.HTTPError:
            raise
        except Exception as e:
            errorMsg = b"<pre class='alert alert-dark text-decoration-none fs-6 font-monospace'>"
            errorMsg += bytes(str(e), encoding="utf-8") + b"<br/>"
            errorMsg += bytes(traceback.format_exc(), encoding="utf-8") + b"</pre>"

            if not response.prepared:
                await response.prepare(request)
            await response.write(errorMsg)
        await response.write_eof()
        return response
    return _handler

import autotest
test = autotest.get_tester(__name__)
from aiohttp.http import HttpVersion10

class MockRequest:
    def __init__(self, path):
        class Writer:
            def __init__(self):
                self.length = ""
                self.output_size = 0
                self.headers = []
                self.content = b""
            async def write_headers(self, *a):
                self.headers.append(a)
            async def write(self, a):
                self.content += a
            async def write_eof(self, a):
                self.content += a
        self.path = path
        self._payload_writer = Writer()
        self.keep_alive = False
        self.version = HttpVersion10
    async def _prepare_hook(*a, **kw):
       pass

@test
async def test_page_render(tmp_path):
    class MockDynamicHtml:
        def __init__(self, response):
            self._response = response
        def handle_request(self, *args, **kwargs):
            return self._response

    handler = dynamic_handler(MockDynamicHtml(["This", "Is",  "The", "Result"]))
    request = MockRequest(path="/")
    response = await handler(request)
    test.eq(b"ThisIsTheResult", request._payload_writer.content)

@test
async def test_error_message_rendering():
    class MockDynamicHtml:
        def handle_request(self, *args, **kwargs):
            1/0
    handler = dynamic_handler(MockDynamicHtml())
    request = MockRequest(path="/")
    response = await handler(request)
    test.truth(request._payload_writer.content.startswith(b"<pre class=\'alert alert-dark text-decoration-none fs-6 font-monospace\'>division by zero<br/>Traceback (most recent call last):\n"))
    test.truth(request._payload_writer.content.endswith(b"\nZeroDivisionError: division by zero\n</pre>"))
