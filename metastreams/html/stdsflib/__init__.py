import sys
import pathlib
import importlib

__all__ = ['builtins']


def load(name):
    importlib.machinery.SourceFileLoader(
            f"{__name__}.{name}",
            pathlib.Path(__file__).with_name(f"{name}.sf").as_posix()
        ).load_module()


# in order of dependency
builtins = ['call_js', 'page', 'login', 'logout', 'prevnextctrl']


# load modules for the side effect of testing
for bi in builtins:
    load(bi)


# delete so they can be dynamically reloaded & watched later
for bi in builtins:
    del sys.modules[__name__ + '.' + bi]

