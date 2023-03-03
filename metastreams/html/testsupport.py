import autotest
test = autotest.get_tester(__name__)

from contextlib import contextmanager

__all__ = ['MockStream', 'CopyTag', 'NoopTag']


@contextmanager
def NoopTag(args):
    yield


class MockStream(dict):
    def map(self, k):
        return self.get(k)


class CopyTag:
    """ Copies the structure created by using "with tag(name):" in code."""
    def __init__(self, root=None):
        self.root = root or []
        self.top = [self.root]
    @contextmanager
    def __call__(self, tag, *attrs, **values):
        child = (tag, attrs, values, [])
        self.top[-1].append(child)
        self.top.append(child[3])
        yield self
        self.top.pop()
    def __getitem__(self, i):
        assert isinstance(self.root, list)
        return CopyTag(self.root[i])
    def __getattr__(self, name):
        if isinstance(self.root, list): # shortcut finds first matching node
            for i in range(len(self.root)):
                if self.root[i][0] == name:
                    node = self.root[i]
                    break
        else:
            node = self.root
        return CopyTag(node[3])
    def __repr__(self):
        return f"CopyTag({self.root!r})"
    def __eq__(self, o):
        return o == self.root
    @property
    def tag(self):
        assert isinstance(self.root, tuple)
        return self.root[0]
    @property
    def attrs(self):
        assert isinstance(self.root, tuple)
        return self.root[1]
    @property
    def values(self):
        assert isinstance(self.root, tuple)
        return self.root[2]
    @property
    def children(self):
        assert isinstance(self.root, tuple)
        return self.root[3]


@test
def copytag_structure():
    def a_template(tag):
        with tag('a', 'NOSHADE', href='link://'):
            yield "https://home.sweet.home"
    cptag = CopyTag()
    list(a_template(cptag))
    test.eq([('a', ('NOSHADE',), {'href': "link://"}, [])], cptag)
    test.eq(('a', ('NOSHADE',), {'href': 'link://'}, []), cptag[0])
    test.eq([], cptag.a)
    node = cptag[0]
    test.eq('a', node.tag)
    test.eq(('NOSHADE',), node.attrs)
    test.eq({'href': 'link://'}, node.values)
    test.eq([], node.children)

