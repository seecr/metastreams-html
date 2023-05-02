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

import sys
import asyncio
import pathlib
from aiohttp import web as aiohttp_web
from aiohttp.test_utils import TestClient, TestServer
from .dynamichtml import DynamicHtml, TemplateImporter

from .static_handler import static_handler
from .dynamic_handler import dynamic_handler

from .paths import usr_share_path

__all__ = ['create_server_app']

async def create_server_app(module_names, index, context=None, static_dirs=(), static_path="/static", enable_sessions=True, session_cookie_name="METASTREAMS_SESSION", additional_routes=None):
    loop = asyncio.get_event_loop()

    # this is untested
    im = await TemplateImporter.install()
    dHtml = DynamicHtml(module_names, default=index, context=context)

    app = aiohttp_web.Application()
    routes = additional_routes or []
    static_dirs += (usr_share_path,)
    routes.append(aiohttp_web.get(static_path + '/{tail:.+}', static_handler(static_dirs, static_path)))
    routes.append(aiohttp_web.get('/favicon.ico', static_handler(static_dirs, '')))
    routes.append(aiohttp_web.route(
        '*', '/{tail:.*}',
        dynamic_handler(dHtml,
            enable_sessions=enable_sessions,
            session_cookie_name=session_cookie_name)))
    app.add_routes(routes)
    return app


async def create_server(port, *args, **kwargs):
    app = await create_server_app(*args, **kwargs)

    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, port=port)
    await site.start()

import autotest
test = autotest.get_tester(__name__)

from .dynamichtml import guarded_path
test.fixture(guarded_path)

@test
async def test_additional_routes(guarded_path):
    keep_meta = sys.meta_path.copy()
    try:
        app = await create_server_app('', "index")
        test.eq(5, len(app.router.routes()))

        app = await create_server_app('', "index", additional_routes=[aiohttp_web.route("get", "/test", lambda: None)])
        test.eq(6, len(app.router.routes()))

        app = await create_server_app('', "index", additional_routes=[
            aiohttp_web.route("get", "/test", lambda: None),
            aiohttp_web.post("/test", lambda: None),
        ])
        test.eq(7, len(app.router.routes()))
    finally:
        for p in sys.meta_path:
            if p not in keep_meta:
                sys.meta_path.remove(p)


@test
async def test_static_dirs(guarded_path):
    (guarded_path/'one').mkdir()
    (guarded_path/'two').mkdir()
    (guarded_path/'one'/'one.html').write_text("I am one")
    (guarded_path/'two'/'two.html').write_text("I am two")
    (guarded_path/'two'/'main.js').write_text("I am main")

    # assure there is a main.js
    app = await create_server_app('', index='index')
    async with TestClient(TestServer(app)) as client:
        result = await client.get('/static/main.js') # there is a main.js in the directory
        test.contains(await result.text(), "import {call_js_all} from")


    app = await create_server_app('', "index", static_dirs=[guarded_path/'one', guarded_path/'two'])

    async with TestClient(TestServer(app)) as client:
        asyncio.create_task(client.start_server())
        result = await client.get('/static/one.html')
        test.eq('I am one', await result.text())
        result = await client.get('/static/two.html')
        test.eq('I am two', await result.text())

        result = await client.get('/static/main.js') # there is a main.js in the directory thats added by default
        test.eq('I am main', await result.text())
