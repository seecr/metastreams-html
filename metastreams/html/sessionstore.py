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

import uuid
import datetime

def timestamp():
    return datetime.datetime.now().timestamp()

class Session:
    def __init__(self, identifier, ttl):
        self._identifier = identifier
        self._last_access = timestamp()
        self._ttl = ttl
        self._data = {}

    @property
    def identifier(self):
        return self._identifier

    def is_expired(self, now=None):
        return self._last_access + self._ttl < (now or timestamp())

    @property
    def last_access(self):
        return self._last_access

    def get(self, *args, **kwargs):
        return self._data.get(*args, **kwargs)

    def pop(self, *args, **kwargs):
        return self._data.pop(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        self._last_access = timestamp()
        return self._data.__setitem__(*args, **kwargs)

    def __getitem__(self, *args, **kwargs):
        return self._data.__getitem__(*args, **kwargs)

    def __iter__(self, *args, **kwargs):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


class SessionStore:
    def __init__(self, ttl=2 * 60 * 60):
        self._sessions = {}
        self._ttl = ttl

    def get_session(self, identifier):
        now = timestamp()
        self._sessions = {k: v for k, v in self._sessions.items() if not v.is_expired(now)}
        return self._sessions.get(identifier, self.new_session())

    def new_session(self):
        identifier = str(uuid.uuid4())
        self._sessions[identifier] = Session(identifier, self._ttl)
        return self._sessions[identifier]

    def __len__(self):
        return len(self._sessions)


import autotest
test = autotest.get_tester(__name__)


@test
def test_session_new_session_if_unknown():
    session_store = SessionStore()

    test.eq(0, len(session_store))
    session = session_store.get_session("some identifier")
    test.eq(1, len(session_store))

    test.eq(id(session), id(session_store.get_session(session.identifier)))

@test
def test_session_store_data():
    session_store = SessionStore()
    session = session_store.new_session()

    session['something'] = 42
    test.eq(42, session['something'])
    test.eq(42, session.get('something'))
    test.eq(None, session.get('nothing'))

@test
def test_sessions_expire():
    session_store = SessionStore(ttl=.1)
    session = session_store.new_session()
    import time
    time.sleep(.1)
    session_revisited = session_store.get_session(session.identifier)
    test.ne(id(session), id(session_revisited))

@test
def test_session_access_keeps_them_alive():
    session_store = SessionStore(ttl=.1)

    session = session_store.new_session()
    import time
    time.sleep(.1)
    test.eq(True, session.is_expired())
    session['data'] = 42
    test.eq(False, session.is_expired())

@test
def test_iter_session():
    session_store = SessionStore()
    session = session_store.new_session()
    test.eq([], [i for i in session])

    session['key'] = 'value'
    test.eq(['key'], [i for i in session])

@test
def test_pop_from_session():
    session_store = SessionStore()
    session = session_store.new_session()
    session['key'] = 'value'
    test.eq(['key'], [i for i in session])
    session.pop('key')
    test.eq([], [i for i in session])

@test
def test_len_session():
    session_store = SessionStore()
    session = session_store.new_session()
    test.eq(0, len(session))
    session['key'] = 'value'
    test.eq(1, len(session))

