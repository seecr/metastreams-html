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
import tempfile
import pathlib
import inspect
import traceback

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib

from .utils import Dict

import logging
logger = logging.getLogger(__name__)

import autotest
test = autotest.get_tester(__name__)


import metastreams.html.stdsflib as stdlib
from ._tag import TagFactory


class TemplateImporter:

    @staticmethod
    async def install():
        if im := next((im for im in sys.meta_path if isinstance(im, TemplateImporter)), None):
            logging.info(f"Watcher: found old TemplateImporter, removing it: {im}.")
            sys.meta_path.remove(im)
            im.task.cancel()
        stdlib_path = stdlib.__path__[0]
        if stdlib_path in sys.path:
            logging.info(f"Importer: stdlib path {stdlib_path!r} already on sys.path.")
        else:
            sys.path.insert(0, stdlib.__path__[0])
        im = TemplateImporter()
        sys.meta_path.append(im)
        im.run(asyncio.get_running_loop())
        await asyncio.sleep(0) # yield task to allow installing watcher task
        return im


    def __init__(self):
        self._watcher = aionotify.Watcher()
        self._path2modname = {}


    def watch_parent_dir(self, qname, sffile):
        parent = sffile.parent.as_posix()
        if parent not in self._watcher.requests:
            self._watcher.watch(parent, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)
        self._path2modname[sffile.as_posix()] = qname


    # https://docs.python.org/3/library/importlib.html#importlib.abc.MetaPathFinder.find_spec
    def find_spec(self, fullname, parent_path, target=None):
        name = fullname.rsplit('.')[-1]
        for parent in parent_path or sys.path:
            sfile = Path(parent)/f"{name}.sf"
            if sfile.is_file():
                self.watch_parent_dir(fullname, sfile)
                return spec_from_loader(fullname, SourceFileLoader(fullname, sfile.as_posix()))
                # after this point, the import might still fail due to (syntax) errors


    async def _run(self):
        await self._watcher.setup(asyncio.get_running_loop())
        while True:
            try:
                event = await self._watcher.get_event()
                if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                    fname = os.path.join(event.alias, event.name)
                    if modName := self._path2modname.get(fname):
                        if mod := sys.modules.get(modName):   # might not have been loaded due to (syntax) errors
                            try:
                                importlib.reload(mod)
                            except Exception as e:
                                logger.exception(f"Exception while reloading {modName}", exc_info=e)
            except Exception as e:
                logging.exception(f"Watcher: loop", exc_info=e)



    def run(self, loop):
        self.task = asyncio.get_running_loop().create_task(self._run())
        return self.task



class DynamicHtml:
    def __init__(self, rootmodule, default="index", context=None):
        self._context = Dict(context) if context else None
        if rootmodule:
            self._rootmodule = rootmodule if isinstance(rootmodule, str) else rootmodule.__name__
        else:
            self._rootmodule = None
        self._default = default


    async def render_page(self, mod, request, response, session=None):
        tag = TagFactory()

        stack = []
        def add_frame(f):
            stack.append(
                traceback.FrameSummary(
                    f.f_code.co_filename,
                    f.f_lineno,
                    f.f_code.co_name))


        async def compose(value):
            if inspect.isasyncgen(value):
                add_frame(value.ag_frame)

                async for v in value:
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each

            elif inspect.isgenerator(value):
                add_frame(value.gi_frame)

                for v in value:
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each
            else:
                yield tag.escape(value)

        try:
            response = mod.main(tag=tag, request=request, response=response, context=self._context, session=session)
            if inspect.isasyncgen(response) or inspect.isgenerator(response):  #TODO test
                try:
                    async for value in compose(response):
                        yield value
                except Exception as e:
                    s = traceback.StackSummary.from_list(stack)
                    for line in s.format():
                        print(line)
                    raise Exception from None
                for line in tag.lines():
                    yield line
            else:
                raise TypeError(f"{mod.main.__qualname__} must be an (async) generator.");

        except HTTPException:
            raise
        except Exception as e:
            logger.exception('DynamicHtml -> render_page Exception:', exc_info=e)
            raise HTTPInternalServerError(body=bytes(str(e), encoding="utf-8")) from None


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
            raise HTTPNotFound(text=request.path)

        return self.render_page(mod, request, response, session=session)


    def _mod_from_request(self, request):
        modname = request.path[1:]
        if not modname:
            modname = self._default
        if self._rootmodule:
            fullname = '.'.join((self._rootmodule, modname))
        else:
            fullname = modname
        try:
            return importlib.import_module(fullname)
        except ModuleNotFoundError as e:
            importlib.invalidate_caches()
            try:
                return importlib.import_module(fullname)
            except ModuleNotFoundError as e:
                raise HTTPNotFound(reason=fullname)
        except Exception as e:
            logger.exception(f"Exception while loading {fullname}:", exc_info=e)
            raise HTTPInternalServerError()


def split_path(path):
    if path[0] == '/':
        path = path[1:]
    path_parts = [part if part else None for part in path.split("/")] + [None]

    module_name, method_name, *_ = path_parts

    return module_name, method_name


class MockRequest:
    def __init__(self, path):
        self.path = path


#keep these to verify later
keep_sys_path = sys.path.copy()
keep_meta_path = sys.meta_path.copy()
keep_modules = sys.modules.copy()



@test
async def remove_old_importer_when_present():
    im0 = await TemplateImporter.install()
    try:
        im1 = await TemplateImporter.install()
        test.eq(im1, sys.meta_path[-1])
        test.ne(im0, im1)
    finally:
        im2 = sys.meta_path.pop()
        test.eq(im1, im2)


@test.fixture
async def sfimporter():
    im0 = await TemplateImporter.install()
    yield im0
    im1 = sys.meta_path.pop()
    assert im1 is im0


@test.fixture
def guarded_path(tmp_path):
    modules = sys.modules.copy()
    assert isinstance(tmp_path, Path)
    path = tmp_path.as_posix()
    sys.path.insert(0, path)
    yield tmp_path
    sys.path.remove(path)
    assert path not in sys.path
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
    from pruts import pruebo

    import inspect
    test.truth(inspect.isfunction(pruts.pruebo.main))


@test
async def load_fixed(sfimporter, guarded_path):
    (guarded_path := guarded_path / "the" / "quick" / "fox").mkdir(parents=True)
    (guarded_path / "lazy_dog.sf").write_text("def main(*a, **kw): yield 'over'")

    from the.quick import fox
    d = DynamicHtml(fox)

    result = await d.handle_request(request=MockRequest(path="/lazy_dog"), response=None)
    test.eq("over", ''.join([i async for i in result]))


@test
def only_one_importer(guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

    import pruts
    currentCount = len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)])

    test.eq(currentCount, len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]))





@test.fixture(guarded_path)

@test
async def reload_template_created_later(sfimporter, guarded_path):
    pruts_path = guarded_path/'pruts'
    pruts_path.mkdir()
    pruebo_path = pruts_path/'pruebo.sf'
    pruebo_path.write_text(f"""import pruts.does_not_exist_yet\n""")

    import pruts   # this works because pruts is on sys.path
    await asyncio.sleep(0.2)
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
    doesnot_exists_yet_path.write_text(f"""
a, b = 42, 43
""")
    await asyncio.sleep(0.1)
    from pruts.does_not_exist_yet import a
    test.eq(42, a)
    from pruts.does_not_exist_yet import b
    test.eq(43, b)


@test
async def reload_after_initially_failing(sfimporter, guarded_path):
    (guarded_path/'failfirst.sf').write_text("await def f(): return 42")
    try:
        import failfirst
        test.fail()
    except SyntaxError:
        pass
    (guarded_path/'failfirst.sf').write_text("async def f(): return 42")
    import failfirst
    test.eq(42, await failfirst.f())


@test
async def wtf_call_wtf_invalidate_caches_wtf(sfimporter, guarded_path):
    for name in ['one', 'two']:
        (dyn_dir := guarded_path / name).mkdir()
        (dyn_dir / f"{name}.sf").write_text(f"def main(**k): yield '{name}'")
    d = DynamicHtml("one")
    result = await d.handle_request(request=MockRequest(path="/one"), response=None)
    test.eq("one", ''.join([i async for i in result]))
    d = DynamicHtml("two")
    result = await d.handle_request(request=MockRequest(path="/two"), response=None)
    test.eq("two", ''.join([i async for i in result]))


@test
async def reload_on_change(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts1").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")

    import pruts1
    import pruts1.pruebo1
    test.eq(1, pruts1.pruebo1.main())

    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 2 ")  # <-- essential space
    await asyncio.sleep(0.1)

    import pruts1.pruebo1
    test.eq(2, pruts1.pruebo1.main())


@test
async def reload_imported_templates(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts2").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("""
import pruts2.pruebo2 as pruebo2

def main(**k):
    return pruebo2.main()
""")
    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 1")

    import pruts2
    import pruts2.pruebo1
    test.eq(1, pruts2.pruebo1.main())

    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 22")
    await asyncio.sleep(0.1)

    test.eq(22, pruts2.pruebo1.main())


@test
async def test_handle_template(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts3").mkdir()
    (dyn_dir / "pruebo.sf").write_text("""
def main(tag, **k):
    with tag("h1"):
        yield "Hello world!"
""")
    d = DynamicHtml("pruts3")
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("<h1>Hello world!</h1>", ''.join([i async for i in result]))


@test
async def test_context_variables(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts4").mkdir()
    (dyn_dir / "pruebo.sf").write_text("""
def main(tag, context, **k):
    with tag("h1"):
        context.container.append(42)
        yield "Hello world!"
""")
    container = []
    d = DynamicHtml("pruts4", context=dict(container=container))
    test.eq([], container)
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("<h1>Hello world!</h1>", ''.join([i async for i in result]))
    test.eq([42], container)


@test
async def test_page_not_found(sfimporter, guarded_path):
    (guarded_path / "pruts5").mkdir()
    d = DynamicHtml("pruts5")

    try:
        await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
        test.truth(False)
    except Exception as e:
        test.truth(isinstance(e, HTTPNotFound))


@test
async def test_reload_with_error(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts6").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    d = DynamicHtml("pruts6")
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("1", ''.join([i async for i in result]))
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
async def test_load_with_error(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts61").mkdir()
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
            test.fail()
        except Exception as e:
            test.truth(isinstance(e, HTTPInternalServerError))
    err_log = err.getvalue()
    test.contains(err_log, 'Exception while loading pruts61.pruebo:')
    test.contains(err_log, 'ZeroDivisionError: division by zero')


@test
async def test_change_to_template_not_yet_loaded(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts7").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    import pruts7
    d = DynamicHtml(pruts7)
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 11")
    await asyncio.sleep(0.1)
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("11", ''.join([i async for i in result]))


@test
async def test_module_imported_with_from(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "here" / "we" / "go").mkdir(parents=True)
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
async def test_module_imported_as_string(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "here" / "we" / "go" / "again").mkdir(parents=True)
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    d = DynamicHtml("here.we.go.again")
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("1", ''.join([i async for i in result]))


@test
async def test_default_page(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
    (dyn_dir / "pruebo.sf").write_text("def main(**k): yield 1")

    d = DynamicHtml("pruts", default="pruebo")
    result = await d.handle_request(request=MockRequest(path="/"), response=None)
    test.eq("1", ''.join([i async for i in result]))


@test
async def use_builtins(sfimporter):
    d = DynamicHtml(None)
    result = await d.handle_request(request=MockRequest(path="/page"), response=None)
    test.eq("", ''.join([i async for i in result]))




#@test
async def test_handle_post_request(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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

#@test
async def test_context_in_post_request(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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
async def test_async_main(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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
async def test_async_main_2(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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
async def test_async_main_3(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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


@test
async def show_decent_stack_trace(sfimporter, guarded_path):
    """ Without doing anything, the exception below results in an incomprehensible
    gibberish with a stack trace of DynamicHtml internals, but no reference to
    'something()', 'another()' or 'main()'. Also the exception is chained, adding
    even more to the incomprehensiblility
    """
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
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
    raise TypeError('aap')

async def main(tag, **kwargs):
    with tag("number"):
        yield something(tag)
        await asyncio.sleep(0.01)
""")
    d = DynamicHtml("pruts")
    try:
        with test.stdout as o:
            async for _ in await d.handle_request(request=MockRequest(path="/pruebo"), response=None):
                pass
    except HTTPInternalServerError:
        pass
    err = o.getvalue()
    test.contains(err, "async def main(tag, **kwargs)")
    test.contains(err, "async def something(tag):")
    test.contains(err, "def another(tag):")



sys.path.remove(stdlib.__path__[0])
sys.modules.pop('page', None)


# verify if stuff is cleaned up
assert keep_sys_path == sys.path, set(keep_sys_path) ^ set(sys.path)
assert keep_meta_path == sys.meta_path
assert keep_modules == sys.modules, keep_modules.keys() ^ sys.modules.keys()
