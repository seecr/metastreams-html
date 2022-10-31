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
import aionotify
from aiohttp.web import HTTPNotFound, HTTPInternalServerError
from pathlib import Path
from urllib.parse import urlencode
from .template import Template
import sys

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib


class Dict(dict):
    def __getattribute__(self, key):
        if key in self:
            return self[key]
        return dict.__getattribute__(self, key)


class TemplateImporter:
    """ finds modules in .sf files """
    def find_spec(self, qname, parent_path, target=None):
        parent_path = parent_path._path[0]
        name = qname.rsplit('.')[-1]
        p = Path(parent_path) / f"{name}.sf"
        if p.is_file():
            s = spec_from_loader(qname, SourceFileLoader(qname, p.as_posix()))
            return s


class DynamicHtml:
    def __init__(self, modules, context=None):
        if len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]) == 0:
            sys.meta_path.append(TemplateImporter())

        self._context = Dict(context) if context else None
        self._watcher = aionotify.Watcher()
        self._modules = [modules] if not isinstance(modules, list) else modules
        for mod in self._modules:
            path = mod.__path__._path[0]
            self._watcher.watch(path, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)

    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                for mod in self._modules:
                    modName = mod.__name__ + "." + event.name[:-3]
                    if modName in sys.modules:
                        importlib.reload(sys.modules[modName])
                        continue


    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())

    def render_page(self, mod, request, response):
        from ._tag import TagFactory
        from weightless.core import compose
        tag = TagFactory()

        def _render(tag, request, response):
            generator = mod.main(tag=tag, request=request, response=response, context=self._context)
            for value in compose(generator):
                yield tag.lines()
                yield tag.escape(value)
            yield tag.lines()

        try:
            for each in compose(_render(tag, request, response)):
                yield each
        except Exception as e:
            raise HTTPInternalServerError(body=bytes(str(e), encoding="utf-8"))

    def handle_request(self, request, response):
        path = request.path
        if path[0] == '/':
            path = path[1:]
        path_parts = path.split("/", 1)
        mod_name = path_parts[0]
        for m in self._modules:
            qname = m.__name__ + "." + mod_name
            if qname not in sys.modules:
                try:
                    importlib.import_module(qname)
                except ModuleNotFoundError as e:
                    raise HTTPNotFound()
            mod = sys.modules[qname]
            return self.render_page(mod, request, response)
        raise HTTPNotFound()


from autotest import test


class MockRequest:
    def __init__(self, path):
        self.path = path


@test
def load_templates_on_create(tmp_path):
    (dyn_dir := tmp_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")
    sys.path.append(tmp_path.as_posix())

    import pruts
    DynamicHtml(pruts)
    from pruts import pruebo

    import inspect
    test.truth(inspect.isfunction(pruts.pruebo.main))


@test
async def load_fixed(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (dyn_dir := tmp_path / "the" / "quick" / "fox").mkdir(parents=True)
    (dyn_dir / "lazy_dog.sf").write_text("def main(*a, **kw): yield 'over'")

    from the.quick import fox
    d = DynamicHtml(fox)

    list(d.handle_request(request=MockRequest(path="/lazy_dog"), response=None))


@test
def only_one_importer(tmp_path):
    (dyn_dir := tmp_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")
    sys.path.append(tmp_path.as_posix())

    import pruts
    DynamicHtml(pruts)
    currentCount = len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)])

    DynamicHtml(pruts)
    test.eq(currentCount, len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]))


@test
def multiple_modules_with_templates(tmp_path):
    for name in ['abra', 'cada', 'bra']:
        (dyn_dir := tmp_path / name).mkdir()
        (dyn_dir / "pruebo.sf").write_text(f"def main(**k): return '{name}'")

    sys.path.append(tmp_path.as_posix())

    import abra, cada, bra
    DynamicHtml([abra, cada, bra])
    from abra import pruebo
    test.eq("abra", pruebo.main())
    from cada import pruebo
    test.eq("cada", pruebo.main())


@test
async def reload_on_change(tmp_path):
    (dyn_dir := tmp_path / "pruts1").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")
    sys.path.append(tmp_path.as_posix())

    import pruts1
    d = DynamicHtml(pruts1)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    import pruts1.pruebo1
    test.eq(1, pruts1.pruebo1.main())

    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 2 ")  # <-- essential space
    await asyncio.sleep(0.1)

    test.eq(2, pruts1.pruebo1.main())

@test
async def reload_imported_templates(tmp_path):
    (dyn_dir := tmp_path / "pruts2").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("""
import pruts2.pruebo2 as pruebo2

def main(**k):
    return pruebo2.main()
""")
    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 1")
    sys.path.append(tmp_path.as_posix())

    import pruts2
    d = DynamicHtml(pruts2)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    import pruts2.pruebo1
    test.eq(1, pruts2.pruebo1.main())

    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 22")
    await asyncio.sleep(0.1)

    test.eq(22, pruts2.pruebo1.main())

@test
async def test_handle_template(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (dyn_dir := tmp_path / "pruts3").mkdir()
    (dyn_dir / "pruebo.sf").write_text("""
def main(tag, **k):
    with tag("h1"):
        yield "Hello world!"
""")

    import pruts3
    d = DynamicHtml(pruts3)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    test.eq(['<h1>', 'Hello world!', '</h1>'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))

@test
async def test_context_variables(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (dyn_dir := tmp_path / "pruts4").mkdir()
    (dyn_dir / "pruebo.sf").write_text("""
def main(tag, context, **k):
    with tag("h1"):
        context.container.append(42)
        yield "Hello world!"
""")

    container = []
    import pruts4
    d = DynamicHtml(pruts4, context=dict(container=container))
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    test.eq([], container)
    test.eq(['<h1>', 'Hello world!', '</h1>'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
    test.eq([42], container)


@test
async def test_page_not_found(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (tmp_path / "pruts5").mkdir()
    import pruts5
    d = DynamicHtml(pruts5)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    try:
        list(d.handle_request(request=MockRequest(path="/pruebo"), response=None))
    except Exception as e:
        test.truth(isinstance(e, HTTPNotFound))


@test
async def test_change_to_template_not_yet_loaded(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (dyn_dir := tmp_path / "pruts7").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    import pruts7
    d = DynamicHtml(pruts7)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 11")
    await asyncio.sleep(0.1)

    test.eq(['11'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))

@test
async def test_module_imported_with_from(tmp_path):
    sys.path.append(tmp_path.as_posix())
    (dyn_dir := tmp_path / "here" / "we" / "go").mkdir(parents=True)
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    from here.we import go
    d = DynamicHtml(go)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    test.eq(['1'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))

    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 11")
    await asyncio.sleep(0.1)
    test.eq(['11'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
