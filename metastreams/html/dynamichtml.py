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
import sys
import inspect
import traceback
import importlib

from aiohttp.web import HTTPNotFound, HTTPException
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

import autotest
test = autotest.get_tester(__name__)


from .utils import Dict
from ._tag import TagFactory
from .sfimporter import TemplateImporter, guarded_path, sfimporter
from .stdsflib import builtins


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

        async def compose(value):
            if inspect.isasyncgen(value):

                async for v in value:
                    stack.extend(traceback.extract_stack(value.ag_frame)) # add current position of generator
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each
                    stack.pop()

            elif inspect.isgenerator(value):

                for v in value:
                    stack.extend(traceback.extract_stack(value.gi_frame)) # add current position of generator
                    for line in tag.lines():
                        yield line
                    async for each in compose(v):
                        yield each
                    stack.pop()
            else:
                yield tag.escape(value)

        response = mod.main(tag=tag, request=request, response=response, context=self._context, session=session)
        if inspect.isasyncgen(response) or inspect.isgenerator(response):  #TODO test
            try:
                async for value in compose(response):
                    yield value
            except HTTPException:  # TODO test
                raise
            except Exception as e:
                tb = e.__traceback__
                most_recent_sf = None
                # find most recent .sf on the stack AND everything from there to the end
                while tb.tb_next:
                    if tb.tb_frame.f_code.co_filename[-3:] == '.sf':
                        most_recent_sf = tb
                    tb = tb.tb_next
                stack.extend(traceback.extract_tb(most_recent_sf or tb)) # recent .sf + possibly down into Python code
                msg = ["Generators Traceback (most recent call last):\n"]
                msg += traceback.StackSummary.from_list(stack).format()
                msg += traceback.format_exception_only(type(e), e)
                for line in msg:
                    print(line, file=sys.stderr, end='')
                raise RuntimeError(f"{e}, see Generators Traceback above")
            for line in tag.lines():
                yield line
        else:
            raise TypeError(f"{mod.main.__qualname__} must be an (async) generator.");


    async def handle_post_request(self, request, session=None):
        modname, method_name = split_path(request.path, 2)
        if method_name is None:
            raise HTTPNotFound()
        mod = self._load_module(modname)

        # TODO: check if allowed to use method, else 405
        try:
            method = getattr(mod, method_name)
        except AttributeError:
            raise HTTPNotFound()

        return_url = await method(request, session=session, context=self._context)
        return return_url


    async def handle_request(self, request, response, session=None): #GET
        modname = split_path(request.path, 1)
        mod = self._load_module(modname)
        return self.render_page(mod, request, response, session=session)

    def _load_module(self, modname):
        if not modname:
            modname = self._default
        if modname in builtins:
            fullname = 'metastreams.html.stdsflib.' + modname
        elif self._rootmodule:
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
                if repr(fullname) in str(e):
                    raise HTTPNotFound(reason=fullname) from None
                raise e from None


def split_path(path, nr):
    if path[0] == '/':
        path = path[1:]
    path_parts = [part if part else None for part in path.split("/")] + [None]*nr
    if nr == 1:
        return path_parts[0]
    return path_parts[:nr]

@test
def test_split_path():
    test.eq([None, None], split_path("/", 2))
    test.eq(["index", None], split_path("/index", 2))
    test.eq(["index", "show"], split_path("/index/show", 2))
    test.eq(["index", "show"], split_path("/index/show/me", 2))
    test.eq(None, split_path("/", 1))
    test.eq('path', split_path("/path/", 1))
    test.eq('path', split_path("/path/some/more/paths", 1))



class MockRequest:
    def __init__(self, path):
        self.path = path


#keep these to verify later
keep_sys_path = sys.path.copy()
keep_meta_path = sys.meta_path.copy()
keep_modules = sys.modules.copy()



test.fixture(guarded_path)
test.fixture(sfimporter)


@test
async def load_fixed(sfimporter, guarded_path):
    (guarded_path := guarded_path / "the" / "quick" / "fox").mkdir(parents=True)
    (guarded_path / "lazy_dog.sf").write_text("def main(*a, **kw): yield 'over'")

    from the.quick import fox
    d = DynamicHtml(fox)

    result = await d.handle_request(request=MockRequest(path="/lazy_dog"), response=None)
    test.eq("over", ''.join([i async for i in result]))



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
async def test_handle_template(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts3").mkdir()
    (dyn_dir / "pruebo.sf").write_text("""
def main(tag, request, **k):
    with tag("h1"):
        yield "Hello world!"
    with tag.p:
        yield "My path: "+request.path
""")
    d = DynamicHtml("pruts3")
    result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    test.eq("<h1>Hello world!</h1><p>My path: /pruebo</p>", ''.join([i async for i in result]))

    result = await d.handle_request(request=MockRequest(path="/pruebo/path/information"), response=None)
    test.eq("<h1>Hello world!</h1><p>My path: /pruebo/path/information</p>", ''.join([i async for i in result]))

@test
async def test_handle_redirect_http_aio_style(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts7").mkdir()
    (dyn_dir / "goto.sf").write_text("""
from aiohttp import web
def main(tag, request, **k):
    raise web.HTTPFound('pruebo')
    yield
""")
    d = DynamicHtml("pruts7")
    a = await d.handle_request(request=MockRequest(path="/goto"), response=None)
    try:
        nr = 0
        async for i in a:
            nr += 1
            print(i)
    except HTTPException as e:
        test.eq(302, e.status)
        test.eq('pruebo', e.location)
    test.eq(0, nr)

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
    try:
        result = await d.handle_request(request=MockRequest(path="/pruebo"), response=None)
        list(i async for i in result)
        test.fail()
    except Exception as e:
        test.isinstance(e, ZeroDivisionError)
    # actual logging and error response is handled upstream


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
    try:
        result = await d.handle_request(request=MockRequest(path="/page"), response=None)
        test.eq("", ''.join([i async for i in result]))
    finally:
        assert 'page' not in sys.modules
        sys.modules.pop('metastreams.html.stdsflib.page')




@test
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



@test
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
async def wwap():
    """ wrap causes an asyncio event loop to be started, forcing the nested test
    to run in a thread; which caused a deadlock on import from metastreams.html,
    without Python detecting it.
    """
    @test
    async def show_right_trace_when_error_deep_in_lib(sfimporter, guarded_path):
        (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
        (dyn_dir / "pruebo.sf").write_text("""
def main(*a, **k):
    import json
    json.dumps(json)  # causes error with some trace
    yield
""")
        d = DynamicHtml("pruts")
        result = []
        try:
            with test.stderr as o:
                async for r in await d.handle_request(request=MockRequest(path="/pruebo"), response=None):
                    result.append(r)
        except RuntimeError:
            pass
        test.eq([], result)
        log = o.getvalue().splitlines()
        test.contains(log[0], "Generators Traceback")
        test.contains(log[1], "pruebo.sf")
        test.contains(log[2], "json.dumps(json)")
        test.contains(log[3], "json/__init__.py")
        test.contains(log[4], ".encode(obj)")
        test.contains(log[5], "encoder.py")
        test.contains(log[6], "iterencode(o,")
        test.contains(log[7], "encoder.py")
        test.contains(log[8], "_iterencode(o,")
        test.contains(log[9], "encoder.py")
        test.contains(log[10], "raise TypeError")
        test.contains(log[11], "not JSON serializable")



@test
async def show_decent_stack_trace(sfimporter, guarded_path):
    """ Without doing anything, the exception below results in an incomprehensible
    gibberish with a stack trace of DynamicHtml internals, but no reference to
    'something()', 'another()' or 'main()'. Also the exception is chained, adding
    even more to the incomprehensiblility
    """
    (dyn_dir := guarded_path / "pruts").mkdir(parents=True)
    (dyn_dir / "pruebo.sf").write_text("""
async def something(tag):
    with tag("something"):
        yield inbetween()
        yield another(tag)

async def inbetween():
    yield "in between"

def another(tag):
    yield "another"
    1/0

async def main(tag, **kwargs):
    yield something(tag)
""")
    d = DynamicHtml("pruts")
    result = []
    try:
        with test.stderr as o:
            async for r in await d.handle_request(request=MockRequest(path="/pruebo"), response=None):
                result.append(r)
    except RuntimeError:
        pass
    test.eq(['<something>', 'in between', 'another'], result)
    err = o.getvalue()
    test.comp.contains(err, "yield inbetween()")  # tests proper pop() async generator
    test.comp.contains(err, 'yield "another"')  # tests proper pop() sync generator
    err = err.splitlines()
    test.contains(err[0], "Traceback (most recent call last):")
    test.contains(err[2], "yield something(tag)")
    test.contains(err[4], "yield another(tag)")
    test.contains(err[6], "1/0")
    test.contains(err[7], "ZeroDivisionError: division by zero")
    test.eq(8, len(err))


# verify if stuff is cleaned up
assert keep_sys_path == sys.path, set(keep_sys_path) ^ set(sys.path)
assert keep_meta_path == sys.meta_path
assert keep_modules == sys.modules, keep_modules.keys() ^ sys.modules.keys()
