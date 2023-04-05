## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2017 SURFmarket https://surf.nl
# Copyright (C) 2017-2018, 2020-2022 Seecr (Seek You Too B.V.) https://seecr.nl
# Copyright (C) 2017 St. IZW (Stichting Informatievoorziening Zorg en Welzijn) http://izw-naz.nl
# Copyright (C) 2020-2021 Data Archiving and Network Services https://dans.knaw.nl
# Copyright (C) 2020-2021 SURF https://www.surf.nl
# Copyright (C) 2020-2021 Stichting Kennisnet https://www.kennisnet.nl
# Copyright (C) 2020-2021 The Netherlands Institute for Sound and Vision https://beeldengeluid.nl
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

from io import StringIO
from functools import partial
from xml.sax.saxutils import quoteattr
import re
from contextlib import contextmanager
from weightless.core import compose
from warnings import warn

from html import escape


__all__ = ['tagable']


def escapeHtml(s, quote=False):
    return escape(s, quote=quote)

def isiter(a):
    try:
        iter(a)
    except TypeError:
        return False
    return True

class Tag(object):
    def __init__(self, html, tagname, _enter_callback=lambda: None, _exit_callback=lambda: None, **attrs):
        self.attrs = {_clearname(k):v for k,v in list(attrs.items())}
        self.html = html
        self._enter_callback = _enter_callback
        self._exit_callback = _exit_callback
        self.attrs['tag'], id_, classes = _splittag(tagname)
        if id_:
            self.set('id', id_)
        for c in classes:
            self.append('class', c)
        self.as_is = AsIs

    def set(self, name, value):
        self.attrs[_clearname(name)] = value
        return self

    def append(self, name, value):
        k = _clearname(name)
        v = self.attrs.get(k)
        if v is None:
            self.attrs[k] = v = []
        v.append(value)
        return self

    def remove(self, name, value):
        self.attrs[_clearname(name)].remove(value)
        return self

    def delete(self, key):
        self.attrs.pop(_clearname(key), None)
        return self

    def __enter__(self):
        self._enter_callback()
        self.tag = self.attrs.pop('tag', None)
        if not self.tag:
            return
        write = self.html.write
        write('<')
        write(self.tag)
        for k, v in sorted((k,v) for k,v in self.attrs.items() if v is not None):
            write(' ')
            write(k)
            write('=')
            if isiter(v) and not isinstance(v, str):
                write(quoteattr(' '.join(str(i) for i in v)))
            else:
                write(quoteattr(str(v)))
        if self.tag in ['br', 'hr']:
            write('/')
            self.tag = None
        if self.tag in ['input']:
            self.tag = None
        write('>')

    def __exit__(self, *a, **kw):
        self._exit_callback()
        if self.tag:
            write = self.html.write
            write('</')
            write(self.tag)
            write('>')

class TagFactory(object):
    def __init__(self):
        self.stream = StringIO()
        self._count = 0

    def write(self, d):
        return self.stream.write(d)

    def _enter_callback(self):
        self._count += 1

    def _exit_callback(self):
        self._count -= 1

    def __call__(self, *args, **kwargs):
        return Tag(self, _enter_callback=self._enter_callback, _exit_callback=self._exit_callback, *args, **kwargs)

    def lines(self):
        if self.stream.tell():
            yield self.stream.getvalue()
            self.stream.truncate(0)
            self.stream.seek(0)

    def escape(self, obj):
        if isinstance(obj, bytes):
            obj = str(obj, encoding='utf-8')
        elif not isinstance(obj, str):
            obj = str(obj)
        if self._count:
            return escapeHtml(obj)
        return obj

    def as_is(self, obj):
        return AsIs(obj)

    def compose(self, f):
        return partial(tag_compose(f, __bw_compat__=True), self)

    def __getattr__(factory, name):
        class ClassCollector:
            def __init__(self, tagname):
                self.tag = None
                self.tagname = tagname
            def __getattr__(self, clzname):
                return self[clzname]
            def __getitem__(self, clzname):
                self.tagname += '.' + clzname
                return self
            def __call__(self, *a, **kw):
                if a and isinstance(a[0], str):
                    self.tagname += '.' + a[0]
                    a = a[1:]
                self.tag = factory(self.tagname, *a, **kw)
                return self
            def __enter__(self):
                if not self.tag:
                    self.tag = factory(self.tagname)
                return self.tag.__enter__()
            def __exit__(self, *a, **kw):
                return self.tag.__exit__(*a, **kw)
        return ClassCollector(name)

def tag_compose(f, __bw_compat__=False):
    @contextmanager
    @compose
    def ctx_man(tag, *args, **kwargs):
        tag._enter_callback()
        try:
            g = compose(f(*args, **kwargs) if __bw_compat__ else f(tag, *args, **kwargs))
            for line in g:
                if line == None:
                    break
                tag.stream.write(escapeHtml(str(line)))
            yield
            for line in g:
                tag.stream.write(escapeHtml(str(line)))
        finally:
            tag._exit_callback()
    return ctx_man


#alias for export
tagable = tag_compose


class AsIs(str):
    def replace(self, *args):
        return self
    def __str__(self):
        return self

_CLEAR_RE = re.compile(r'^([^_].*[^_])_$')
def _clearname(name):
    m = _CLEAR_RE.match(name)
    if m:
        return m.group(1)
    return name

def _splittag(tagname):
    if not tagname:
        return tagname, None, []
    tagname, _, classstring = tagname.partition('.')
    tagname, _, identifier = tagname.partition('#')
    return tagname, identifier, [c for c in classstring.split('.') if c]


import autotest
test = autotest.get_tester(__name__)


def as_template(func):
    def _render(func):
        tag = TagFactory()
        generator = func(tag=tag)
        for value in compose(generator):
            yield tag.lines()
            yield tag.escape(value)
        yield tag.lines()
    return ''.join(list(compose(_render(func))))


@test
def test_composition():
    def main(tag):
        def my_gen():
            yield "hello"

        def snd_gen(s):
            yield s

        @tag_compose
        def my_tag(tag, start, stop=None):
            yield snd_gen(start)
            with tag('div'):
                with tag('h1'):
                    yield           # here goes the stuff within 'with'
            yield stop
        with tag('head'):
            with my_tag(tag, 'forword', stop='afterword'):
                with tag('p'):
                    yield my_gen()
    test.eq('<head>forword<div><h1><p>hello</p></h1></div>afterword</head>', as_template(main))


@test
def test_compose_escapes_content():
    def main(tag):
        def my_gen():
            yield "4: <>&"

        def snd_gen():
            yield "2: <>&"

        @tag_compose
        def my_tag(tag):
            yield "1: <>&"
            yield snd_gen()
            with tag('div'):
                with tag('h1'):
                    yield           # here goes the stuff within 'with'
            yield "5: <>&"

        with tag('body'):
            with my_tag(tag):
                yield "3: <>&"
                with tag('p'):
                    yield my_gen()
        test.eq('<body>1: &lt;&gt;&amp;2: &lt;&gt;&amp;<div><h1>3: &lt;&gt;&amp;<p>4: &lt;&gt;&amp;</p></h1></div>5: &lt;&gt;&amp;</body>', as_template(main))


@test
def test_attrs():
    s = StringIO()
    with Tag(s, 'a', **{'key': 'value'}, do_not_include=None, do_include=0):
        s.write('data')
    test.eq('<a do_include="0" key="value">data</a>', s.getvalue())


@test
def test_append_to_list_attr():
    s = StringIO()
    t = Tag(s, 'a', class_=['value'])
    t.append('class', 'value2')
    with t:
        s.write('data')
    test.eq('<a class="value value2">data</a>', s.getvalue())


@test
def test_append_to_empty_list_attr():
    s = StringIO()
    t = Tag(s, 'a', class_=[])
    t.append('class', 'value')
    t.append('class', 'value2')
    t.append('class', 'value3')
    with t:
        s.write('data')
    test.eq('<a class="value value2 value3">data</a>', s.getvalue())


@test
def test_append_to_nothing_creates_list_attr():
    s = StringIO()
    t = Tag(s, 'a')
    t.append('class', 'value')
    with t:
        s.write('data')
    test.eq('<a class="value">data</a>', s.getvalue())


@test
def test_append_to_non_list_attr():
    s = StringIO()
    t = Tag(s, 'a', some_attr='not-a-list')
    try:
        t.append('some_attr', 'value')
        assert False
    except AttributeError:
        pass

@test
def test_remove_from_list_attr():
    s = StringIO()
    t = Tag(s, 'a', class_=['value', 'value2'])
    t.remove('class', 'value2')
    with t:
        s.write('data')
    test.eq('<a class="value">data</a>', s.getvalue())


@test
def test_clear_name():
    test.eq('class', _clearname('class'))
    test.eq('class', _clearname('class_'))
    test.eq('_class', _clearname('_class'))
    test.eq('_class_', _clearname('_class_'))
    test.eq('class__', _clearname('class__'))


@test
def test_reserved_word_attrs():
    s = StringIO()
    with Tag(s, 'a', class_=['class'], if_='if'):
        s.write('data')
    test.eq('<a class="class" if="if">data</a>', s.getvalue())


@test
def test_tag_in_template():
    def main(tag):
        yield 'voorwoord'
        with tag('p'):
            yield 'paragraph'
        yield 'nawoord'
    test.eq('voorwoord<p>paragraph</p>nawoord', as_template(main))

    def main(tag):
        yield 'voorwoord'
        with tag('p'):
            with tag('i'):
                yield 'italic'
    test.eq('voorwoord<p><i>italic</i></p>', as_template(main))

    def main(tag):
        with tag('p'):
            with tag('i'):
                yield 'italic'
    test.eq('<p><i>italic</i></p>', as_template(main))


@test
def test_escape_text_within_tags():
    def main(tag):
        yield "&"
    test.eq('&', as_template(main))

    def main(tag):
        yield "&"
        with tag('p'):
            yield "&"
    test.eq('&<p>&amp;</p>', as_template(main))

    def main(tag):
        yield "&a"
        with tag('p'):
            yield "&b"
            yield " &c"
        yield "&d"
    test.eq('&a<p>&amp;b &amp;c</p>&d', as_template(main))

    def main(tag):
        with tag('p'):
            yield "&a"
            yield " &b"
    test.eq('<p>&amp;a &amp;b</p>', as_template(main))

    def main(tag):
        with tag('p'):
            yield "&a"
            with tag('i'):
                yield "&b"
            yield "&c"
        yield "&d"
    test.eq('<p>&amp;a<i>&amp;b</i>&amp;c</p>&d', as_template(main))

    def main(tag):
        with tag('p'):
            yield "&a"
        yield "&b"
        with tag('p'):
            yield "&c"
        yield "&d"
    test.eq('<p>&amp;a</p>&b<p>&amp;c</p>&d', as_template(main))


@test
def test_escape_other_stuff():
    def main(tag):
        with tag('p'):
            yield ['&', 'noot']
    test.eq("<p>['&amp;', 'noot']</p>", as_template(main))


@test
def test_asis():
    def main(tag):
            with tag('p'):
                yield tag.as_is('<i>dit</i>')
    test.eq('<p><i>dit</i></p>', as_template(main))


@test
def test_mixin_bytes():
    def main(tag):
        with tag('p'):
            yield b"Bytes bite"
    test.eq('<p>Bytes bite</p>', as_template(main))


@test
def test_attributes_converted_to_string():
    def main(tag):
        with tag('div', value=3):
            yield 42
    test.eq('<div value="3">42</div>', as_template(main))


@test
def test_dot_turns_into_classes():
    def main(tag):
        with tag('div.w100.ph3'):
            yield 42
    test.eq('<div class="w100 ph3">42</div>', as_template(main))

    def main(tag):
        with tag('div.w100.ph3', class_=['other']):
            yield 42
    test.eq('<div class="other w100 ph3">42</div>', as_template(main))

    def main(tag):
        with tag('div#identifier.w100.ph3', class_=['other']):
            yield 42
    test.eq('<div class="other w100 ph3" id="identifier">42</div>', as_template(main))

@test
def dot_notation():
    def main(tag):
        with tag.aap:
            yield 'noot'
    test.eq("<aap>noot</aap>", as_template(main))
    def main(tag):
        with tag.aap.classA:
            yield 'noot'
    test.eq("""<aap class="classA">noot</aap>""", as_template(main))
    def main(tag):
        with tag.aap['clz-3']:
            yield 'noot'
    test.eq("""<aap class="clz-3">noot</aap>""", as_template(main))
    def main(tag):
        with tag.aap.classA(attr=99):
            yield 'noot'
    test.eq("""<aap attr="99" class="classA">noot</aap>""", as_template(main))
    def main(tag):
        with tag.aap.classA('classB.class-c', attr=42):
            yield 'noot'
    test.eq("""<aap attr="42" class="classA classB class-c">noot</aap>""", as_template(main))
