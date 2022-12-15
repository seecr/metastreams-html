import sys
import pathlib

class PathModify:
    def __init__(self):
        self._paths = []

    def add_path(self, path):
        if isinstance(path, pathlib.Path):
            path = path.as_posix()
        if path not in self._paths:
            self._paths.append(path)
            sys.path.insert(0, path)

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        for path in self._paths:
            if (i := sys.path.index(path)) > -1:
                sys.path.pop(i)


import autotest
test = autotest.get_tester(__name__)


@test
def test_cleanup():
    l = len(sys.path)
    with PathModify() as pm:
        pm.add_path("/tmp")
        test.eq(l + 1, len(sys.path))
        test.truth("/tmp" in sys.path)
    test.eq(l, len(sys.path))

@test
def test_str_or_path(tmp_path):
    l = len(sys.path)
    with PathModify() as pm:
        pm.add_path(tmp_path)
        test.eq(l + 1, len(sys.path))
        test.truth(tmp_path.as_posix() in sys.path)
    test.eq(l, len(sys.path))
