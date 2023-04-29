## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2023 Seecr (Seek You Too B.V.) https://seecr.nl
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
builtins = ['call_js', 'page', 'login', 'logout', 'prevnextctrl', 'jstests']
assert all(sf.stem in builtins for sf in pathlib.Path(__file__).parent.glob("*.sf"))


# load modules for the side effect of testing
for bi in builtins:
    load(bi)


# delete so they can be dynamically reloaded & watched later
for bi in builtins:
    del sys.modules[__name__ + '.' + bi]

