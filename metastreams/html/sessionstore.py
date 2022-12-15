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

    def __setitem__(self, *args, **kwargs):
        self._last_access = timestamp()
        return self._data.__setitem__(*args, **kwargs)

    def __getitem__(self, *args, **kwargs):
        return self._data.__getitem__(*args, **kwargs)


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

