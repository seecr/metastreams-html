## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2022-2023 Seecr (Seek You Too B.V.) https://seecr.nl
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

from pathlib import Path
from aiohttp import web as aiohttp_web

import mimetypes
mimetypes.init()
# Override defaults (for redhat systems)
mimetypes.add_type("application/javascript", ".js")

# Add types
mimetypes.add_type("application/xhtml+xml", ".xhtml")
# XSD removed in Debian Bullsey package media-types (responsible for /etc/mime.types)
mimetypes.add_type("application/xml", ".xsd")


def content_type(filename):
    if not isinstance(filename, Path):
        filename = Path(filename)

    type_ = "text/plain"
    try:
        type_ = mimetypes.types_map[filename.suffix]
    except KeyError:
        pass
    return type_


def static_handler(static_dirs, static_path):
    static_dirs = static_dirs if isinstance(static_dirs, list) else [static_dirs]

    async def _handler(request):
        if not (requested_path := request.path).startswith(static_path):
            raise aiohttp_web.HTTPNotFound()

        requested_file = requested_path[len(static_path + '/'):]
        matches = [fname for static_dir in static_dirs if (fname := Path(static_dir) / requested_file).is_file()]
        if len(matches) == 0:
            raise aiohttp_web.HTTPNotFound()
        fname = matches[0]

        mimeType = content_type(fname)
        fname = str(fname)
        response = aiohttp_web.StreamResponse(
            status=200,
            reason='OK',
            headers={'Content-Type': mimeType},
        )
        await response.prepare(request)

        with open(fname, 'rb') as fp:
            while True:
                data = fp.read(1024)
                if len(data) == 0:
                    break
                await response.write(data)
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
async def no_file_for_static_handler(tmp_path):
    handler = static_handler(tmp_path, "/static")
    try:
        await handler(MockRequest(path="/static/does_not_exist"))
        assert False
    except aiohttp_web.HTTPNotFound as e:
        test.eq('Not Found', str(e))

@test
async def static_handler_path_mismatch(tmp_path):
    handler = static_handler(tmp_path, "/static")
    try:
        await handler(MockRequest(path="/this/does_not_exist"))
        assert False
    except aiohttp_web.HTTPNotFound as e:
        test.eq('Not Found', str(e))

@test
async def serve_file(tmp_path):
    handler = static_handler(tmp_path, "/static")
    (tmp_path / "test-file.txt").write_text("These are the contents")
    request = MockRequest(path="/static/test-file.txt")
    response = await handler(request)

    test.eq({"Content-Type", "Date", "Server"}, set(dict(response.headers).keys()))
    test.eq(b"These are the contents", request._payload_writer.content)


@test
def test_get_content_type():
    test.eq("text/css", content_type("pruebo.css"))
    test.eq("text/plain", content_type("pruebo.we_have_no_idea"))


@test
async def test_multiple_static_directories(tmp_path):
    (dir_a := tmp_path / "a").mkdir()
    (dir_b := tmp_path / "b").mkdir()
    (dir_b / "file.txt").write_text("Hello World")
    
    handler = static_handler([dir_a, dir_b], "/static")
    request = MockRequest(path="/static/file.txt")
    response = await handler(request)

    test.eq(b"Hello World", request._payload_writer.content)

    (dir_a / "file.txt").write_text("Goodbye World")
    request = MockRequest(path="/static/file.txt")
    response = await handler(request)

    test.eq(b"Goodbye World", request._payload_writer.content)
