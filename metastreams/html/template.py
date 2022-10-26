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

from weightless.core import compose

class Template:
    def __init__(self, funcs=None):
        self.__dict__ = funcs or {}

    def updateFuncs(self, funcs):
        self.__dict__ = funcs

    def __call__(self, *a, **kw):
        if 'main' in self.__dict__:
            return self._render(*a, **kw)
        raise RuntimeError("Main not found")

    def _render(self, *args, **kwargs):
        from ._tag import TagFactory
        tag = TagFactory()
        template = self.__dict__['main']

        def _render(*a, **kw):
            generator = template(*a, tag=tag, **kw)
            for value in compose(generator):
                yield tag.lines()
                yield tag.escape(value)
            yield tag.lines()
        for each in compose(_render(*args, **kwargs)):
            yield each


from autotest import test


@test
async def test_render_simple_page(tmp_path):

    def main(**k):
        yield 'hello world'
    def main2(): pass

    t = Template(funcs=dict(main=main, main2=main2))

    g = t()
    test.eq(['hello world'], list(g))


@test
async def test_render_simple_page_2(tmp_path):
    def main(tag, **k):
        with tag("div"):
            yield "hello world"
    t = Template(funcs=dict(main=main))

    g = t()
    test.eq(['<div>', 'hello world', '</div>'], list(g))

#@test
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


#@test
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

