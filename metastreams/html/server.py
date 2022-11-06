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

from pathlib import Path
from metastreams.html import DynamicHtml
import asyncio
from aiohttp import web as aiohttp_web
from importlib import import_module
import magic
mime = magic.Magic(mime=True)

def static_handler(static_dir, static_path):
    async def _handler(request):
        fname = Path(static_dir) / request.path[len(static_path+'/'):]
        if not fname.is_file():
            raise aiohttp_web.HTTPNotFound()

        fname = str(fname)
        mimeType = mime.from_file(fname)
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


async def create_server(port, module_names, static_dir, static_path="/static"):
    imported_modules = [import_module(name) for name in module_names]

    loop = asyncio.get_event_loop()

    dHtml = DynamicHtml(imported_modules)
    dHtml.run(loop)

    app = aiohttp_web.Application()
    app.add_routes([
        aiohttp_web.get(static_path + '/{tail:.+}', static_handler(static_dir, static_path)),
        aiohttp_web.get('/{tail:.*}', dynamic_handler(dHtml)),
    ])

    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, port=port)
    await site.start()
