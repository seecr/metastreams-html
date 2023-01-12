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

import asyncio
from aiohttp import web as aiohttp_web
from importlib import import_module
from .dynamichtml import DynamicHtml

from .static_handler import static_handler
from .dynamic_handler import dynamic_handler


def create_server_app(module_names, index, context=None, static_dirs=None, static_path="/static", enable_sessions=True, session_cookie_name="METASTREAMS_SESSION"):
    imported_modules = [import_module(name) for name in module_names]

    loop = asyncio.get_event_loop()

    dHtml = DynamicHtml(imported_modules, default=index, context=context)
    dHtml.run(loop)

    app = aiohttp_web.Application()
    routes = []
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
    app = create_server_app(*args, **kwargs)

    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, port=port)
    await site.start()
