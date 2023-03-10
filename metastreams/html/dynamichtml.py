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
import os.path

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib

from .utils import PathModify, RevertImports, Dict, guarded_path

import logging
logger = logging.getLogger(__name__)

import autotest
test = autotest.get_tester(__name__)


class TemplateImporter:

    @staticmethod
    async def install():
        im = next((im for im in sys.meta_path if isinstance(im, TemplateImporter)), None)
        if not im:
            im = TemplateImporter()
            sys.meta_path.append(im)
            im.run(asyncio.get_running_loop())
        await asyncio.sleep(0) # yield task to allow installing watcher task
        return im


    def __init__(self):
        self._watcher = aionotify.Watcher()
        self._map = {}


    def watch_parent_dir(self, qname, sffile):
        parent = sffile.parent.as_posix()
        if parent not in self._watcher.requests:
            self._watcher.watch(parent, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)
        self._map[sffile.as_posix()] = qname


    # https://docs.python.org/3/library/importlib.html#importlib.abc.MetaPathFinder.find_spec
    def find_spec(self, fullname, parent_path, target=None):
        name = fullname.rsplit('.')[-1]
        for parent in parent_path or sys.path:
            sfile = Path(parent)/f"{name}.sf"
            if sfile.is_file():
                self.watch_parent_dir(fullname, sfile)
                return spec_from_loader(fullname, SourceFileLoader(fullname, sfile.as_posix()))


    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                fname = os.path.join(event.alias, event.name)
                if fname in self._map:
                    modName = self._map[fname]
                    try:
                        importlib.reload(sys.modules[modName])
                    except Exception as e:
                        logger.exception(f"Exception while reloading {modName}", exc_info=e)

    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())
        return self.task



class DynamicHtml:
    def __init__(self, modules, default="index", context=None):
        self._context = Dict(context) if context else None
        self._modules = [modules] if not isinstance(modules, list) else modules
        self._modules = [importlib.import_module(mod) if isinstance(mod, str) else mod for mod in self._modules]
        self._default = default

    async def render_page(self, mod, request, response, session=None):
        from ._tag import TagFactory
        import inspect
        tag = TagFactory()

        async def compose(value):
            if inspect.isasyncgen(value):
                async for v in value:
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each
            elif inspect.isgenerator(value):
                for v in value:
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each
            else:
                yield tag.escape(value)

        try:
            generator = mod.main(tag=tag, request=request, response=response, context=self._context, session=session)
            async for value in compose(generator):
                yield value
            for line in tag.lines():
                yield line

        except HTTPException:
            raise
        except Exception as e:
            logger.exception('DynamicHtml -> render_page Exception:', exc_info=e)
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


    async def handle_request(self, request, response, session=None):
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
                logger.exception(f"Exception while loading {name}:", exc_info=e)
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


class MockRequest:
    def __init__(self, path):
        self.path = path



@test
async def load_importer_as_singleton():
    im0 = await TemplateImporter.install()
    try:
        im1 = await TemplateImporter.install()
        test.eq(im0, sys.meta_path[-1])
        test.eq(im0, im1)
        test.eq(id(im0), id(im1))
    finally:
        im2 = sys.meta_path.pop()
        test.eq(im0, im2)


@test.fixture
async def sfimporter():
    im0 = await TemplateImporter.install()
    yield im0
    im1 = sys.meta_path.pop()
    assert im1 is im0


@test.fixture
def guarded_path(tmp_path):
    modules = sys.modules.copy()
    assert isinstance(tmp_path, pathlib.Path)
    path = tmp_path.as_posix()
    sys.path.insert(0, path)
    yield tmp_path
    p = sys.path.pop(0)
    assert p == path
    for m in set(sys.modules):
        if m not in modules:
            sys.modules.pop(m)

@test
async def load_top_level_sf(sfimporter, guarded_path):
    (guarded_path/'x.sf').write_text("a=42")
    from x import a
    test.eq(42, a)


@test
async def load_templates_on_create(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

    import pruts
    DynamicHtml(pruts)
    from pruts import pruebo

    import inspect
    test.truth(inspect.isfunction(pruts.pruebo.main))


@test
async def load_fixed(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "the" / "quick" / "fox").mkdir(parents=True)
            (dyn_dir / "lazy_dog.sf").write_text("def main(*a, **kw): yield 'over'")

            from the.quick import fox
            d = DynamicHtml(fox)

            result = await d.handle_request(request=MockRequest(path="/lazy_dog"), response=None)
            test.eq("over", ''.join([i async for i in result]))


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





@test.fixture(guarded_path)

#@test
async def reload_template_created_later(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            pruts_path = tmp_path/'pruts'
            pruts_path.mkdir()
            pruebo_path = pruts_path/'pruebo.sf'
            pruebo_path.write_text(f"""import pruts.does_not_exist_yet\n""")

            import pruts   # this works because pruts is on sys.path
            d = DynamicHtml([])  # this automagically adds an imported and an inotify listener
            task = d.run(asyncio.get_running_loop())
            await asyncio.sleep(0.2)
            assert d._watcher._fd
            try:
                import pruts.pruebo
                test.fail()
            except ImportError as e:
                test.eq("No module named 'pruts.does_not_exist_yet'", str(e))
            doesnot_exists_yet_path = pruts_path/'does_not_exist_yet.sf'
            doesnot_exists_yet_path.write_text(f"""a=10\n""")
            await asyncio.sleep(0.2)
            import pruts.pruebo
            from pruts.does_not_exist_yet import a
            test.eq(10, a)


            print("++++++++++++++++++++++++++++++")
            doesnot_exists_yet_path.write_text(f"""
a, b = 42, 43
# FTWDDD



""")
            await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
            print("-----", d._watcher.requests)
            from pruts.does_not_exist_yet import a
            test.eq(42, a)
            from pruts.does_not_exist_yet import b
            test.eq(43, b)
            task.cancel()




@test
async def multiple_modules_resolve(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            for name in ['one', 'two']:
                (dyn_dir := tmp_path / name).mkdir()
                (dyn_dir / f"{name}.sf").write_text(f"def main(**k): yield '{name}'")

            d = DynamicHtml(["one", "two"])

            result = await d.handle_request(request=MockRequest(path="/two"), response=None)
            test.eq("two", ''.join([i async for i in result]))


@test
async def reload_on_change(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts1").mkdir()
            (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")

            import pruts1
            d = DynamicHtml(pruts1)

            import pruts1.pruebo1
            test.eq(1, pruts1.pruebo1.main())

            (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 2 ")  # <-- essential space
            await asyncio.sleep(0.1)

            import pruts1.pruebo1
            test.eq(2, pruts1.pruebo1.main())

@test
async def reload_imported_templates(sfimporter, tmp_path):
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
            await asyncio.sleep(0.1)

            import pruts2.pruebo1
            test.eq(1, pruts2.pruebo1.main())

            (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 22")
            await asyncio.sleep(0.1)

            test.eq(22, pruts2.pruebo1.main())


@test
async def load_new_template_and_add_to_watcher(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            pass


@test
async def test_handle_template(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts3").mkdir()
            (dyn_dir / "pruebo.sf").write_text("""
def main(tag, **k):
    with tag("h1"):
        yield "Hello world!"
""")

            d = DynamicHtml("pruts3")
            await asyncio.sleep(0.1)
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("<h1>Hello world!</h1>", ''.join([i async for i in result]))

@test
async def test_context_variables(sfimporter, tmp_path):
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
            d = DynamicHtml("pruts4", context=dict(container=container))
            await asyncio.sleep(0.1)


            test.eq([], container)
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("<h1>Hello world!</h1>", ''.join([i async for i in result]))
            test.eq([42], container)


@test
async def test_page_not_found(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (tmp_path / "pruts5").mkdir()
            d = DynamicHtml("pruts5")

            try:
                await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
                test.truth(False)
            except Exception as e:
                test.truth(isinstance(e, HTTPNotFound))


@test
async def test_reload_with_error(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts6").mkdir()
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")
            logged_exceptions = []

            d = DynamicHtml("pruts6")
            d._log_exception = lambda *a, **kw: logged_exceptions.append((a, kw))

            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("1", ''.join([i async for i in result]))
            test.eq([], logged_exceptions)
            with test.stderr as err:
                (dyn_dir / "pruebo.sf").write_text("""
1/0

def main(**k):
    yield 11
""")
                await asyncio.sleep(0.1)
            err_log = err.getvalue()
            test.contains(err_log, 'Exception while reloading pruts6.pruebo')
            test.contains(err_log, 'ZeroDivisionError: division by zero')

            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("1", ''.join([i async for i in result])) # previous value


@test
async def test_load_with_error(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts61").mkdir()
            (dyn_dir / "pruebo.sf").write_text("""
1/0

def main(**k):
    yield 11
""")
            d = DynamicHtml("pruts61")
            with test.stderr as err:
                try:
                    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
                    list(i async for i in result)
                    test.truth(False)
                except Exception as e:
                    test.truth(isinstance(e, HTTPInternalServerError))
            err_log = err.getvalue()
            test.contains(err_log, 'Exception while loading pruts61.pruebo:')
            test.contains(err_log, 'ZeroDivisionError: division by zero')


@test
async def test_change_to_template_not_yet_loaded(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts7").mkdir()
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            import pruts7
            d = DynamicHtml(pruts7)

            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 11")
            await asyncio.sleep(0.1)
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("11", ''.join([i async for i in result]))

@test
async def test_module_imported_with_from(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "here" / "we" / "go").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            from here.we import go
            d = DynamicHtml(go)

            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("1", ''.join([i async for i in result]))

            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 11")
            await asyncio.sleep(0.1)
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("11", ''.join([i async for i in result]))


@test
async def test_module_imported_as_string(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "here" / "we" / "go" / "again").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            d = DynamicHtml("here.we.go.again")
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("1", ''.join([i async for i in result]))


@test
async def test_default_page(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

            d = DynamicHtml("pruts", default="pruebo")
            result = await d.handle_request(request=MockRequest(path="/"), response=None)
            test.eq("1", ''.join([i async for i in result]))


@test
async def test_specific_default_page(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir1 := tmp_path / "pruts91").mkdir(parents=True)
            (dyn_dir1 / "pruebo.sf").write_text("async def main(**k): yield 1")
            (dyn_dir2 := tmp_path / "pruts92").mkdir(parents=True)
            (dyn_dir2 / "pruebo.sf").write_text("async def main(**k): yield 2")

            d = DynamicHtml(["pruts91", "pruts92"], default="pruts92.pruebo")

            result = await d.handle_request(request=MockRequest(path="/"), response=None)
            test.eq("2", ''.join([i async for i in result]))


@test
async def test_handle_post_request(sfimporter, tmp_path):
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

async def main(**k):
    yield str(WORDS)
""")

            d = DynamicHtml("pruts")
            return_url = await d.handle_post_request(request=MockRequest(path="/pruebo/something"))
            test.eq("/pruebo", return_url)

            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq("['one', 'two']", ''.join([i async for i in result]))

@test
async def test_context_in_post_request(sfimporter, tmp_path):
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


@test
async def test_async_main(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("""
import asyncio

async def main(tag, **kwargs):
    with tag("number"):
        yield "42"
        await asyncio.sleep(0.1)
""")
            d = DynamicHtml("pruts")
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq(['<number>', '42', '</number>'], [i async for i in result])

@test
async def test_async_main_2(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("""
import asyncio

async def something(tag):
    with tag("something"):
        yield "42"

async def main(tag, **kwargs):
    with tag("number"):
        yield something(tag)
        await asyncio.sleep(0.1)
""")
            d = DynamicHtml("pruts")
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq('<number><something>42</something></number>', ''.join([i async for i in result]))
@test
async def test_async_main_3(sfimporter, tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        with RevertImports():
            (dyn_dir := tmp_path / "pruts").mkdir(parents=True)
            (dyn_dir / "pruebo.sf").write_text("""
import asyncio

async def something(tag):
    with tag("something"):
        yield another(tag)
        await asyncio.sleep(0.01)
        yield "something"

def another(tag):
    with tag("another"):
        yield "another"

async def main(tag, **kwargs):
    with tag("number"):
        yield something(tag)
        await asyncio.sleep(0.01)
""")
            d = DynamicHtml("pruts")
            result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
            test.eq('<number><something><another>another</another>something</something></number>', ''.join([i async for i in result]))
