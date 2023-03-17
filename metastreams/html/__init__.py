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

from .sessionstore import SessionStore
from .cookie import Cookie
from .dynamichtml import DynamicHtml, Dict
from .static_handler import static_handler
from .dynamic_handler import dynamic_handler
from .testsupport import *

usr_share_path = "/usr/share/metastreams-html"

from pathlib import Path                                                   #DO_NOT_DISTRIBUTE
my_dir = Path(__file__).absolute()                                         #DO_NOT_DISTRIBUTE
usr_share_path = (my_dir.parent.parent.parent / 'usr-share').as_posix()    #DO_NOT_DISTRIBUTE

from .server import *
from .passwordfile2 import *
from ._tag import *
