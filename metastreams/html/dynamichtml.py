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

import asyncio
import aionotify
from aiohttp.web import HTTPException, HTTPFound, HTTPNotFound, HTTPInternalServerError
from pathlib import Path
from urllib.parse import urlencode
import sys

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib
import logging

from .utils import PathModify, RevertImports, Dict

class TemplateImporter:
    """ finds modules in .sf files """
    def find_spec(self, qname, parent_path, target=None):
        parent_path_list = parent_path if isinstance(parent_path, list) else parent_path._path
        name = qname.rsplit('.')[-1]
        p = Path(parent_path_list[0]) / f"{name}.sf"
        if p.is_file():
            s = spec_from_loader(qname, SourceFileLoader(qname, p.as_posix()))
            return s


class DynamicHtml:
    def __init__(self, modules, default="index", context=None):
        if len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]) == 0:
            sys.meta_path.append(TemplateImporter())

        self._context = Dict(context) if context else None
        self._watcher = aionotify.Watcher()
        self._modules = [modules] if not isinstance(modules, list) else modules
        self._modules = [importlib.import_module(mod) if isinstance(mod, str) else mod for mod in self._modules]
        for mod in self._modules:
            path = mod.__path__._path[0]
            self._watcher.watch(path, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)
        self._default = default

    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                for mod in self._modules:
                    modName = mod.__name__ + "." + event.name[:-3]
                    if modName in sys.modules:
                        try:
                            importlib.reload(sys.modules[modName])
                        except Exception as e:
                            self._log_exception(f"Exception while reloading {modName}:", exc_info=e)
                        continue

    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())

    def _log_exception(self, msg, exc_info):
        logger = logging.getLogger(__name__)
        logger.exception(msg, exc_info=exc_info)

    def render_page(self, mod, request, response, session=None):
        from ._tag import TagFactory
        from weightless.core import compose
        tag = TagFactory()

        def _render(tag, request, response):
            generator = mod.main(tag=tag, request=request, response=response, context=self._context, session=session)
            for value in compose(generator):
                yield tag.lines()
                yield tag.escape(value)
            yield tag.lines()

        try:
            for each in compose(_render(tag, request, response)):
                yield each
        except HTTPException:
            raise
        except Exception as e:
            self._log_exception('DynamicHtml -> render_page Exception:', exc_info=e)
            raise HTTPInternalServerError(body=bytes(str(e), encoding="utf-8"))

    async def handle_post_request(self, request, session=None):
        if (mod := self._mod_from_request(request)) is None:
            raise HTTPNotFound()

        _, method_name = split_path(request.path)
        if method_name is None:
            raise HTTPNotFound()

        # TODO: check if allowed to use method, else 405
        try:
            method = getattr(mod, method_name)
        except AttributeError:
            raise HTTPNotFound()

        return_url = await method(request, session=session, context=self._context)
        return return_url


    def handle_request(self, request, response, session=None):
        if (mod := self._mod_from_request(request)) is None:
            raise HTTPNotFound()

        return self.render_page(mod, request, response, session=session)

    def _mod_from_request(self, request):
        mod = None

        def _load_module(name):
            try:
                importlib.import_module(name)
                return sys.modules[name]
            except ModuleNotFoundError:
                pass
            except Exception as e:
                self._log_exception(f"Exception while loading {name}:", exc_info=e)
                raise HTTPInternalServerError()

        path = request.path
        if path == "/":
            if "." in self._default:
                mod = sys.modules.get(self._default, _load_module(self._default))
            else:
                path = "/" + self._default

        if mod is None:
            mod_name, _ = split_path(path)
            for m in self._modules:
                qname = m.__name__ + "." + mod_name
                if (mod := sys.modules.get(qname, _load_module(qname))):
                    break
        return mod

def split_path(path):
    if path[0] == '/':
        path = path[1:]
    path_parts = [part if part else None for part in path.split("/")] + [None]

    module_name, method_name, *_ = path_parts

    return module_name, method_name


import autotest
test = autotest.get_tester(__name__)


class MockRequest:
    def __init__(self, path):
        self.path = path


@test
def load_templates_on_create(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir()
            (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

            import pruts
            DynamicHtml(pruts)
            from pruts import pruebo

            import inspect
            test.truth(inspect.isfunction(pruts.pruebo.main))


@test
async def load_fixed(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "the" / "quick" / "fox").mkdir(parents=True)
            (dyn_dir / "lazy_dog.sf").write_text("def main(*a, **kw): yield 'over'")

            from the.quick import fox
            d = DynamicHtml(fox)

            list(d.handle_request(request=MockRequest(path="/lazy_dog"), response=None))


@test
def only_one_importer(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir()
            (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

            import pruts
            DynamicHtml(pruts)
            currentCount = len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)])

            DynamicHtml(pruts)
            test.eq(currentCount, len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]))


@test
def multiple_modules_with_templates(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            for name in ['abra', 'cada', 'bra']:
                (dyn_dir := tmp_path / name).mkdir()
                (dyn_dir / "pruebo.sf").write_text(f"def main(**k): return '{name}'")

            import abra, cada, bra
            DynamicHtml([abra, cada, bra])
            from abra import pruebo
            test.eq("abra", pruebo.main())
            from cada import pruebo
            test.eq("cada", pruebo.main())


@test
def multiple_modules_resolve(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            for name in ['one', 'two']:
                (dyn_dir := tmp_path / name).mkdir()
                (dyn_dir / f"{name}.sf").write_text(f"def main(**k): yield '{name}'")

            import one, two
            d = DynamicHtml([one, two])

            test.eq(['two'], list(d.handle_request(request=MockRequest(path="/two"), response=None)))

@test
async def reload_on_change(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts1").mkdir()
            (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")

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
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts2").mkdir()
            (dyn_dir / "pruebo1.sf").write_text("""
import pruts2.pruebo2 as pruebo2

def main(**k):
    return pruebo2.main()
""")
            (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 1")

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
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
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
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
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
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
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
async def test_reload_with_error(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts6").mkdir()
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")
            logged_exceptions = []

            import pruts6
            d = DynamicHtml(pruts6)
            d._log_exception = lambda *a,**kw: logged_exceptions.append((a,kw))
            d.run(asyncio.get_running_loop())
            await asyncio.sleep(0.1)

            test.eq(['1'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
            test.eq([], logged_exceptions)
            (dyn_dir / "pruebo.sf").write_text("""
1/0

def main(**k):
    yield 11
""")
            await asyncio.sleep(0.1)

            test.eq(['1'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
            test.eq(1, len(logged_exceptions))
            test.eq(('Exception while reloading pruts6.pruebo:', ), logged_exceptions[0][0])
            test.truth(isinstance(logged_exceptions[0][1]['exc_info'], ZeroDivisionError))


@test
async def test_load_with_error(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts61").mkdir()
            (dyn_dir / "pruebo.sf").write_text("""
1/0

def main(**k):
    yield 11
""")
            logged_exceptions = []

            import pruts61
            d = DynamicHtml(pruts61)
            d._log_exception = lambda *a, **kw: logged_exceptions.append((a, kw))

            test.eq([], logged_exceptions)
            try:
                test.eq([], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
                test.truth(False)
            except Exception as e:
                test.truth(isinstance(e, HTTPInternalServerError))
            test.eq(1, len(logged_exceptions))
            test.eq(('Exception while loading pruts61.pruebo:', ), logged_exceptions[0][0])
            test.truth(isinstance(logged_exceptions[0][1]['exc_info'], ZeroDivisionError))


@test
async def test_change_to_template_not_yet_loaded(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
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
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
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


@test
async def test_module_imported_as_string(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "here" / "we" / "go" / "again").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            d = DynamicHtml("here.we.go.again")
            test.eq(['1'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))


@test
async def test_default_page(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            d = DynamicHtml("pruts", default="pruebo")
            test.eq(['1'], list(d.handle_request(request=MockRequest(path="/"), response=None)))


@test
async def test_specific_default_page(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir1 := tmp_path / "pruts91").mkdir(parents=True)
            (dyn_dir1 / "pruebo.sf").write_text("def main(**k): yield 1")
            (dyn_dir2 := tmp_path / "pruts92").mkdir(parents=True)
            (dyn_dir2 / "pruebo.sf").write_text("def main(**k): yield 2")

            d = DynamicHtml(["pruts91", "pruts92"], default="pruts92.pruebo")
            test.eq(['2'], list(d.handle_request(request=MockRequest(path="/"), response=None)))


@test
async def test_handle_post_request(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("""
WORDS = []

import asyncio

async def something(request, **kwargs):
    WORDS.append("one")
    await asyncio.sleep(0.1)
    WORDS.append("two")

    return "/pruebo"

def main(**k):
    yield str(WORDS)
""")

            d = DynamicHtml("pruts")
            return_url = await d.handle_post_request(request=MockRequest(path="/pruebo/something"))
            test.eq("/pruebo", return_url)

            answer = list(d.handle_request(request=MockRequest(path="/pruebo"), response=None))
            test.eq(["['one', 'two']"], answer)


@test
async def test_context_in_post_request(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("""
import asyncio

async def something(request, context, **kwargs):
    context.words.append("one")
    await asyncio.sleep(0.1)
    context.words.append("two")

    return "/pruebo"
""")

            words = []
            d = DynamicHtml("pruts", context=dict(words=words))
            return_url = await d.handle_post_request(request=MockRequest(path="/pruebo/something"))
            test.eq("/pruebo", return_url)
            test.eq(["one", "two"], words)

@test
def test_split_path():
    test.eq((None, None), split_path("/"))
    test.eq(("index", None), split_path("/index"))
    test.eq(("index", "show"), split_path("/index/show"))
