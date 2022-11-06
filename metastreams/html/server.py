from pathlib import Path
from metastreams.html import DynamicHtml
import asyncio

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

async def create_server(loop, port, module_names, static_dir, static_path="/static"):
    imported_modules = [importlib.import_module(name) for name in module_names]

    dHtml = DynamicHtml(imported_modules)
    dHtml.run(loop)

    app = aiohttp_web.Application()
    app.add_routes([
        aiohttp_web.get('/static/{tail:.+}', static_handler),
        aiohttp_web.get('/{tail:.*}', dlc_handler(dHtml)),
    ])

    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, port=port)
    await site.start()
