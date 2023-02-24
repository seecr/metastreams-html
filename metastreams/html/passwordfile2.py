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

from json import load, dump
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from os import chmod, rename
from os.path import isfile
from stat import S_IWRITE, S_IREAD
from pathlib import Path

ph = PasswordHasher()

class PasswordFile2(object):
    def __init__(self, filepath, user_resolve=None):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        if filepath.is_dir():
            filepath /= "passwd"
        self._storage = _Storage(filepath.as_posix())
        self._user_resolve = user_resolve

    def addUser(self, username, password):
        if self.hasUser(username):
            raise ValueError('User already exists.')
        self._storage.set(username, ph.hash(password))
        if self._user_resolve is not None:
            self._user_resolve.add_user(username)

    def removeUser(self, username):
        self._storage.remove(username)
        if self._user_resolve is not None:
            self._user_resolve.remove_user(username)

    def validateUser(self, username, password):
        hashed = self._storage.get(username)
        try:
            result = hashed is not None and ph.verify(hashed, password)
            if result and ph.check_needs_rehash(hashed):
                self.setPassword(username, password)
            return result
        except VerifyMismatchError:
            return False
        except InvalidHash:
            raise ValueError(f'Unexpected hash for user {username}, check file!')

    def setPassword(self, username, password):
        if not self.hasUser(username):
            raise ValueError('User does not exist.')
        self._storage.set(username, ph.hash(password))

    def listUsernames(self):
        return self._storage.listkeys()

    def hasUser(self, username):
        return username in self._storage.listkeys()
    
    def resolve_user(self, username):
        if self._user_resolve is None:
            return None
        return self._user_resolve.resolve_user(username)

class _Storage(object):
    version = 3
    def __init__(self, filepath):
        self._filepath = filepath
        self._loadUsers()

    def set(self, username, hashed):
        d = self._loadUsers()
        d[username] = hashed
        self._storeUsers(d)

    def remove(self, username):
        d = self._loadUsers()
        d.pop(username, None)
        self._storeUsers(d)

    def get(self, username):
        return self._loadUsers().get(username)

    def listkeys(self):
        return list(sorted(self._loadUsers().keys()))

    def _loadUsers(self):
        if not isfile(self._filepath):
            return {}
        with open(self._filepath, 'r') as fp:
            data = load(fp)
            if not data.get('version') == self.version:
                raise ValueError("Unexpected version")
            return data['users']

    def _storeUsers(self, users):
        if not isfile(self._filepath):
            with open(self._filepath, 'w') as fp:
                dump({'version': self.version, 'users':{}}, fp)
        with open(self._filepath, 'r') as fp:
            data = load(fp)
            data['users'] = users
            with open(self._filepath+'~', 'w') as wfp:
                dump(data, wfp)
        rename(self._filepath+'~', self._filepath)
        chmod(self._filepath, S_IREAD | S_IWRITE)

__all__ = ['PasswordFile2']


import autotest
test = autotest.get_tester(__name__)

@test
def test_add_user(tmp_path):
    pf = PasswordFile2(tmp_path / "passwd")
    test.truth(not pf.hasUser("aap"))
    pf.addUser("aap", "noot")
    test.truth(pf.hasUser("aap"))

    try:
        pf.addUser("aap", "noot")
        test.fail()
    except ValueError as e:
        test.eq("User already exists.", str(e))

@test
def test_add_user_resolve(tmp_path):
    calls = []
    class Users:
        def add_user(self, username):
            calls.append(username)

    pf = PasswordFile2(tmp_path / "passwd", user_resolve=Users())
    test.eq(0, len(calls))
    pf.addUser("aap", "noot")
    test.eq(1, len(calls))
    try:
        pf.addUser("aap", "noot")
        test.fail()
    except ValueError as e:
        test.eq("User already exists.", str(e))
    test.eq(1, len(calls))

@test
def test_remove_user_resolve(tmp_path):
    calls = []
    class Users:
        def remove_user(self, username):
            calls.append(username)
    pf = PasswordFile2(tmp_path / "passwd")
    pf.addUser("aap", "noot")

    pf = PasswordFile2(tmp_path / "passwd", user_resolve=Users())
    test.eq(0, len(calls))
    pf.removeUser("aap")
    test.eq(1, len(calls))


@test
def test_resolve_user(tmp_path):
    pf = PasswordFile2(tmp_path / "passwd")
    test.eq(None, pf.resolve_user("aap"))
    pf.addUser("aap", "noot")
    test.eq(None, pf.resolve_user("aap"))

    class UserResolve:
        def resolve_user(self, username):
            return {"name": username, "admin": False}
    pf = PasswordFile2(tmp_path / "passwd", user_resolve=UserResolve())
    user = pf.resolve_user("aap")
    test.eq({'name': 'aap', 'admin': False}, user)

@test
def test_filename_password_file(tmp_path):
    pf = PasswordFile2(tmp_path / "passwd")
    test.eq((tmp_path / "passwd").as_posix(), pf._storage._filepath)
    pf = PasswordFile2(tmp_path)
    test.eq((tmp_path / "passwd").as_posix(), pf._storage._filepath)
