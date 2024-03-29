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
from aiohttp.web import HTTPFound
import json
from urllib.parse import parse_qs

class Dict(dict):
    def __getattribute__(self, key):
        if key in self:
            return self[key]
        return dict.__getattribute__(self, key)

def check_user_in_session(session):
    return session and session.get("user") is not None

def check_admin_in_session(session):
    return session and (user := session.get("user")) is not None and user.get("admin", False) is True

def user_required(func):
    def check_user(*args, **kwargs):
        session = kwargs.get("session")
        if check_user_in_session(session):
            return func(*args, **kwargs)
        raise HTTPFound('/login')
    return check_user

def user_admin(func):
    def check_user(*args, **kwargs):
        session = kwargs.get("session")
        if check_admin_in_session(session):
            return func(*args, **kwargs)
        raise HTTPFound('/login')
    return check_user


async def arguments_from_request(request, required, convert=None):
    convert = convert or {}
    body = await request.text()
    try:
        values = {each['name']: each['value'] for each in json.loads(body) if each['name'] in required}
    except json.decoder.JSONDecodeError:
        values = {key: value[0] for key, value in parse_qs(body, keep_blank_values=True).items() if key in required}

    if required.intersection(set(values.keys())) != required:
        return Dict()

    for name, method in convert.items():
        try:
            values[name] = method(values[name])
        except:
            del values[name]
    return Dict(values)


import autotest
test = autotest.get_tester(__name__)


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

@test
def test_user_admin(tmp_path):
    called = []
    @user_admin
    def sub(**kwargs):
        called.append(None)

    try:
        sub()
        test.fail()
    except HTTPFound as e:
        test.eq("/login", e.location)
    test.eq(0, len(called))

    sub(session={"user": {"admin": True}})
    test.eq(1, len(called))


@test
async def test_arguments_from_request():
    class Request:
        def __init__(self, text):
            self._text = text
        async def text(self):
            return self._text

    test.eq({}, await arguments_from_request(Request(""), required=set()))
    test.eq({}, await arguments_from_request(Request(""), required={"arg"}))

    test.eq({'arg': ""}, await arguments_from_request(Request("arg="), required={"arg"}))
    test.eq({'arg': "1"}, await arguments_from_request(Request("arg=1"), required={"arg"}))
    test.eq({'arg': "1"}, await arguments_from_request(Request("arg=1&another=2"), required={"arg"}))
    test.eq({'arg': 1}, await arguments_from_request(Request("arg=1"), required={"arg"}, convert=dict(arg=int)))
    test.eq({}, await arguments_from_request(Request("arg=1"), required={"arg"}, convert=dict(arg=lambda x: int(x)/0)))

    test.eq({'arg': ""}, await arguments_from_request(Request('[{"name": "arg", "value": ""}]'), required={"arg"}))
    test.eq({'arg': "1"}, await arguments_from_request(Request('[{"name": "arg", "value": "1"}]'), required={"arg"}))
    test.eq({'arg': "1"}, await arguments_from_request(Request('[{"name": "arg", "value": "1"}, {"name": "other", "value": "2"}]'), required={"arg"}))
    test.eq({'arg': 1}, await arguments_from_request(Request('[{"name": "arg", "value": "1"}]'), required={"arg"}, convert=dict(arg=int)))
    test.eq({}, await arguments_from_request(Request('[{"name": "arg", "value": "1"}]'), required={"arg"}, convert=dict(arg=lambda x: int(x)/0)))


