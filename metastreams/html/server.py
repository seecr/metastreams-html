from pathlib import Path
from metastreams.html import DynamicHtml
import asyncio
from aiohttp import web as aiohttp_web
from importlib import import_module

async def static_handler(request):
    staticDir = Path(__file__).parent / "static"
    fname = staticDir / request.path[len('/static/'):]
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
        aiohttp_web.get('/static/{tail:.+}', static_handler),
        aiohttp_web.get('/{tail:.*}', dynamic_handler(dHtml)),
    ])

    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, port=port)
    await site.start()
