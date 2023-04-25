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

import asyncio
import aionotify
from pathlib import Path
import sys
import os.path
import inspect

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib

import logging
logger = logging.getLogger(__name__)

import autotest
test = autotest.get_tester(__name__)


class TemplateImporter:

    @staticmethod
    async def install():
        if im := next((im for im in sys.meta_path if isinstance(im, TemplateImporter)), None):
            logging.info(f"Watcher: found old TemplateImporter, removing it: {im}.")
            sys.meta_path.remove(im)
            im.task.cancel()
        im = TemplateImporter()
        sys.meta_path.append(im)
        im.run(asyncio.get_running_loop())
        await asyncio.sleep(0) # yield task to allow installing watcher task
        return im


    def __init__(self):
        self._watcher = aionotify.Watcher()
        self._path2modname = {}


    def watch_parent_dir(self, qname, sffile):
        parent = sffile.parent.as_posix()
        if parent not in self._watcher.requests:
            self._watcher.watch(parent, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)
        self._path2modname[sffile.as_posix()] = qname


    # https://docs.python.org/3/library/importlib.html#importlib.abc.MetaPathFinder.find_spec
    def find_spec(self, fullname, parent_path, target=None):
        name = fullname.rsplit('.')[-1]
        for parent in parent_path or sys.path:
            sfile = Path(parent)/f"{name}.sf"
            if sfile.is_file():
                self.watch_parent_dir(fullname, sfile)
                return spec_from_loader(fullname, SourceFileLoader(fullname, sfile.as_posix()))
                # after this point, the import might still fail due to (syntax) errors


    async def _run(self):
        await self._watcher.setup(asyncio.get_running_loop())
        while True:
            try:
                event = await self._watcher.get_event()
                if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                    fname = os.path.join(event.alias, event.name)
                    if modName := self._path2modname.get(fname):
                        if mod := sys.modules.get(modName):   # might not have been loaded due to (syntax) errors
                            try:
                                importlib.reload(mod)
                            except Exception as e:
                                logger.exception(f"Exception while reloading {modName}", exc_info=e)
            except Exception as e:
                logging.exception(f"Watcher: loop", exc_info=e)



    def run(self, loop):
        self.task = asyncio.get_running_loop().create_task(self._run())
        return self.task


#keep these to verify later
keep_sys_path = sys.path.copy()
keep_meta_path = sys.meta_path.copy()
keep_modules = sys.modules.copy()



@test
async def remove_old_importer_when_present():
    im0 = await TemplateImporter.install()
    try:
        im1 = await TemplateImporter.install()
        test.eq(im1, sys.meta_path[-1])
        test.ne(im0, im1)
    finally:
        im2 = sys.meta_path.pop()
        test.eq(im1, im2)


@test.fixture
async def sfimporter():
    im0 = await TemplateImporter.install()
    yield im0
    im1 = sys.meta_path.pop()
    assert im1 is im0


@test.fixture
def guarded_path(tmp_path):
    modules = sys.modules.copy()
    assert isinstance(tmp_path, Path)
    path = tmp_path.as_posix()
    sys.path.insert(0, path)
    yield tmp_path
    sys.path.remove(path)
    assert path not in sys.path
    for m in set(sys.modules):
        if m not in modules:
            sys.modules.pop(m)


@test
async def load_top_level_sf(sfimporter, guarded_path):
    (guarded_path/'x.sf').write_text("a=42")
    from x import a
    test.eq(42, a)


@test
async def load_templates_on_create(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

    import pruts
    from pruts import pruebo

    import inspect
    test.truth(inspect.isfunction(pruts.pruebo.main))


@test
def only_one_importer(guarded_path):
    (dyn_dir := guarded_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")

    import pruts
    currentCount = len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)])

    test.eq(currentCount, len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]))





@test.fixture(guarded_path)

@test
async def reload_template_created_later(sfimporter, guarded_path):
    pruts_path = guarded_path/'pruts'
    pruts_path.mkdir()
    pruebo_path = pruts_path/'pruebo.sf'
    pruebo_path.write_text(f"""import pruts.does_not_exist_yet\n""")

    import pruts   # this works because pruts is on sys.path
    await asyncio.sleep(0.2)
    try:
        import pruts.pruebo
        test.fail()
    except ImportError as e:
        test.eq("No module named 'pruts.does_not_exist_yet'", str(e))
    doesnot_exists_yet_path = pruts_path/'does_not_exist_yet.sf'
    doesnot_exists_yet_path.write_text(f"""a=10\n""")
    await asyncio.sleep(0.2)
    import pruts.pruebo
    from pruts.does_not_exist_yet import a
    test.eq(10, a)
    doesnot_exists_yet_path.write_text(f"""
a, b = 42, 43
""")
    await asyncio.sleep(0.1)
    from pruts.does_not_exist_yet import a
    test.eq(42, a)
    from pruts.does_not_exist_yet import b
    test.eq(43, b)


@test
async def reload_after_initially_failing(sfimporter, guarded_path):
    (guarded_path/'failfirst.sf').write_text("await def f(): return 42")
    try:
        import failfirst
        test.fail()
    except SyntaxError:
        pass
    (guarded_path/'failfirst.sf').write_text("async def f(): return 42")
    import failfirst
    test.eq(42, await failfirst.f())


@test
async def reload_on_change(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts1").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")

    import pruts1
    import pruts1.pruebo1
    test.eq(1, pruts1.pruebo1.main())

    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 2 ")  # <-- essential space
    await asyncio.sleep(0.1)

    import pruts1.pruebo1
    test.eq(2, pruts1.pruebo1.main())


@test
async def reload_imported_templates(sfimporter, guarded_path):
    (dyn_dir := guarded_path / "pruts2").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("""
import pruts2.pruebo2 as pruebo2

def main(**k):
    return pruebo2.main()
""")
    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 1")

    import pruts2
    import pruts2.pruebo1
    test.eq(1, pruts2.pruebo1.main())

    (dyn_dir / "pruebo2.sf").write_text("def main(**k): return 22")
    await asyncio.sleep(0.1)

    test.eq(22, pruts2.pruebo1.main())



# verify if stuff is cleaned up
assert keep_sys_path == sys.path, set(keep_sys_path) ^ set(sys.path)
assert keep_meta_path == sys.meta_path
assert keep_modules == sys.modules, keep_modules.keys() ^ sys.modules.keys()
