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
from .dynamichtml import DynamicHtml, TemplateImporter

from .static_handler import static_handler
from .dynamic_handler import dynamic_handler

__all__ = ['create_server_app']

async def create_server_app(module_names, index, context=None, static_dirs=None, static_path="/static", enable_sessions=True, session_cookie_name="METASTREAMS_SESSION", additional_routes=None):
    loop = asyncio.get_event_loop()

    # this is untested
    im = await TemplateImporter.install()
    dHtml = DynamicHtml(module_names, default=index, context=context)

    app = aiohttp_web.Application()
    routes = additional_routes or []
    routes.append(aiohttp_web.static(static_path, pathlib.Path(__file__).parent.parent.parent/'usr-share'))
    if static_dirs is not None:
        routes.append(aiohttp_web.get(static_path + '/{tail:.+}', static_handler(static_dirs, static_path)))
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
        test.eq(3, len(app.router.routes()))

        app = await create_server_app('', "index", additional_routes=[aiohttp_web.route("get", "/test", lambda: None)])
        test.eq(4, len(app.router.routes()))

        app = await create_server_app('', "index", additional_routes=[
            aiohttp_web.route("get", "/test", lambda: None),
            aiohttp_web.post("/test", lambda: None),
        ])
        test.eq(5, len(app.router.routes()))
    finally:
        for p in sys.meta_path:
            if p not in keep_meta:
                sys.meta_path.remove(p)
