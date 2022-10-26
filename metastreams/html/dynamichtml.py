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
from aiohttp.web import HTTPNotFound
from pathlib import Path
from urllib.parse import urlencode
from json import dumps, loads
from .template import Template

class DynamicHtml:
    def __init__(self, directories, additional_globals=None):
        self._original_import = globals()['__builtins__']['__import__']
        self.directories = [Path(directory) if not isinstance(directory, Path) else directory for directory in (directories if isinstance(directories, list) else [directories])]
        self.templates = {}
        self._additional_globals = additional_globals or {}
        self._load_templates()
        self._watcher = None
        self._init_inotify()

    def _init_inotify(self):
        self._watcher = aionotify.Watcher()
        for path in self.directories:
            self._watcher.watch(str(path), aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)

    def _load_templates(self):
        for directory in self.directories:
            for path in directory.glob("*.sf"):
                self._load_template(path)

    def __import__(self, moduleName, globals, *a, **kw):
        if moduleName in self.templates:
            #globals[moduleName] = self.templates[moduleName]
            return self.templates[moduleName]
        for each in self.directories:
            if (each / f"{moduleName}.sf").is_file():
                self._load_template(each / f"{moduleName}.sf")
                if moduleName not in globals:
                    globals[moduleName] = self.templates[moduleName]
                return self.templates[moduleName]

        result = self._original_import(moduleName, globals, *a, **kw)
        globals[moduleName] = result
        return result

    def _load_template(self, filepath):
        module_globals = {'__builtins__': __builtins__, 'urlencode': urlencode}
        module_globals['__builtins__']['__import__'] = self.__import__
        module_globals.update(self._additional_globals)
        module_locals = {}
        module_name = filepath.stem
        if module_name not in self.templates:
            self.templates[module_name] = Template()
        with open(filepath, "rb") as f:
            exec(compile(f.read(), filepath, "exec"), module_globals, module_locals)
        module_globals.update(module_locals)
        self.templates[module_name].updateFuncs(module_globals)

    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                self._load_template(Path(event.alias)/event.name)

    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())

    def render_page(self, name, request=None, response=None):
        template = self.templates[name]
        for each in template(request=request, response=response):
            yield each

    def handle_request(self, request, response):
        path = request.path
        if path[0] == '/':
            path = path[1:]
        path_parts = path.split("/", 1)
        if path_parts[0] in self.templates:
            return self.render_page(path_parts[0], request, response)
        raise HTTPNotFound()


from autotest import test


@test
def create_ensures_directories_is_list(tmp_path):
    d = DynamicHtml(tmp_path)
    test.eq([tmp_path], d.directories)

@test
def ensure_directories_are_paths(tmp_path):
    d = DynamicHtml(str(tmp_path))
    test.eq([tmp_path], d.directories)
    test.truth(isinstance(d.directories[0], Path))



@test
def load_templates_on_create(tmp_path):
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    d = DynamicHtml(tmp_path)
    test.eq(['pruebo'], list(d.templates.keys()))


@test
async def reload_templates_on_change(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("def main(**k): return 'version 1'")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)
    test.eq('version 1', d.templates['pruebo'].main())
    (tmp_path / "pruebo.sf").write_text("def main(**k): return 'version 2'")
    await asyncio.sleep(.01)
    test.eq('version 2', d.templates['pruebo'].main())


@test
async def reload_templates_on_create(tmp_path):
    loop = asyncio.get_running_loop()
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)
    test.eq([], list(d.templates.keys()))
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    await asyncio.sleep(.01)
    test.eq(1, len(d.templates))
    test.eq(["pruebo"], list(d.templates.keys()))


@test
async def reload_templates_on_move(tmp_path):
    path_1 = tmp_path / "path_1"
    path_1.mkdir()
    path_2 = tmp_path / "path_2"
    path_2.mkdir()
    (path_2 / "pruebo.sf").write_text("def main(**k): pass")

    loop = asyncio.get_running_loop()
    d = DynamicHtml(path_1)
    d.run(loop)
    await asyncio.sleep(.01)
    test.eq([], list(d.templates.keys()))

    (path_2 / "pruebo.sf").rename(path_1 / "pruebo.sf")
    await asyncio.sleep(.01)
    test.eq(["pruebo"], list(d.templates.keys()))


@test
async def test_render_simple_page(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
def main(**k):
    yield 'hello world'

def main2(): pass
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)

    g = d.render_page("pruebo", request=None, response=None)
    from weightless.core import compose
    test.eq(['hello world'], list(compose(g)))


@test
async def test_render_simple_page_2(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
def main(tag, **k):
    with tag("div"):
        yield "hello world"
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)

    g = d.render_page("pruebo", request=None, response=None)
    test.eq(['<div>', 'hello world', '</div>'], list(g))

@test
async def test_render_simple_page_3(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo1.sf").write_text("""
import pruebo2

def main(tag, **k):
    with tag("div"):
        yield pruebo2.func(tag, "hello world")
""")
    (tmp_path / "pruebo2.sf").write_text("""
def func(tag, arg):
    with tag("h1"):
        yield arg
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)

    g = d.render_page("pruebo1", request=None, response=None)
    test.eq(['<div><h1>', 'hello world', '</h1></div>'], list(g))


@test
async def test_render_page_with_function(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
def main(tag, **k):
    with tag("div"):
        yield func(tag, "hello world")

def func(tag, arg):
    with tag("h1"):
        yield arg
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)

    g = d.render_page("pruebo", request=None, response=None)
    test.eq(['<div><h1>', 'hello world', '</h1></div>'], list(g))



@test
async def test_import_other_modules(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
from sys import version
import sys

def main(tag, **k):
    with tag("p"):
        yield sys.version
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)
    import sys
    g = d.render_page("pruebo", request=None, response=None)
    test.eq(['<p>', sys.version, '</p>'], list(g))


@test
async def test_change_imported_template(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo1.sf").write_text("""
import pruebo2

def main(**kw):
    yield pruebo2.func()
""")
    (tmp_path / "pruebo2.sf").write_text("""
def func(**kw):
    yield 1
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.1)

    g = d.render_page("pruebo1", request=None, response=None)
    test.eq(['1'], list(g))

    (tmp_path / "pruebo2.sf").write_text("""
def func(**kw):
    yield 2
""")
    await asyncio.sleep(.1)

    g = d.render_page("pruebo1", request=None, response=None)
    test.eq(['2'], list(g))


@test
async def test_basic_python_stuff(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
def main(**kw):
    t = True
    f = False
    n = None
    i = int("42")
    s = str(42)
    d = dict()
    l = list()
    s = sorted([])
    u = urlencode(dict())
    yield "Works!"
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.1)

    g = d.render_page("pruebo", request=None, response=None)
    test.eq(['Works!'], list(g))



@test
async def test_additional_globals(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo1.sf").write_text("""
def main(**kw):
    yield THE_GLOBAL
""")
    d = DynamicHtml(tmp_path, additional_globals={'THE_GLOBAL': 1})
    d.run(loop)
    await asyncio.sleep(.1)

    g = d.render_page("pruebo1", request=None, response=None)
    test.eq(['1'], list(g))


@test
async def test_handle_request(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("""
def main(**kw):
    yield "It works!"
""")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.1)

    class MockRequest:
        def __init__(this, path):
            this.path = path

    test.eq(['It works!'], list(d.handle_request(request=MockRequest(path="/pruebo"), response=None)))
    test.eq(['It works!'], list(d.handle_request(request=MockRequest(path="/pruebo/again"), response=None)))


@test
async def test_handle_request_not_found(tmp_path):
    loop = asyncio.get_running_loop()
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.1)

    class MockRequest:
        def __init__(this, path):
            this.path = path

    exception = None
    try:
        d.handle_request(request=MockRequest(path="/pruebo"), response=None)
    except HTTPNotFound as e:
        exception = e
    test.truth(isinstance(exception, HTTPNotFound))

