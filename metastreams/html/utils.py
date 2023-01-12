import sys
import pathlib
from aiohttp.web import HTTPFound

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


class RevertImports:
    def __init__(self):
        self._modules = sys.modules.copy()

    def __enter__(self):
        return self

    def __exit__(self, type, values, tb):
        for each in list(sys.modules.keys()):
            if each not in self._modules:
                sys.modules.pop(each)


class Dict(dict):
    def __getattribute__(self, key):
        if key in self:
            return self[key]
        return dict.__getattribute__(self, key)

def user_required(func):
    def check_user(*args, **kwargs):
        session = kwargs.get("session")
        if session and session.get("user") is not None:
            return func(*args, **kwargs)
        raise HTTPFound('/login')
    return check_user


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


@test
def test_clean_up_imports(tmp_path):
    with PathModify() as pm:
        pm.add_path(tmp_path)
        (tmp_path / "clean_up_test.py").write_text("def main(): pass")
        with RevertImports():
            import clean_up_test
            test.truth("clean_up_test" in sys.modules)

        test.truth("clean_up_test" not in sys.modules)

@test
def test_user_required(tmp_path):
    called = []
    @user_required
    def sub(**kwargs):
        called.append(None)

    try:
        sub()
        assert False
    except HTTPFound as e:
        test.eq("/login", e.location)
    test.eq(0, len(called))

    try:
        sub(session={})
        assert False
    except HTTPFound as e:
        test.eq("/login", e.location)
    test.eq(0, len(called))

    try:
        sub(session={"user": None})
    except HTTPFound as e:
        test.eq("/login", e.location)
    test.eq(0, len(called))

    sub(session={"user": True})
    test.eq(1, len(called))

