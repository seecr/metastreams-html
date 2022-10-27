## begin license ##
#
# "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
# It is also known as "DynamicHtml" or "Seecr Html".
#
# Copyright (C) 2022 Seecr (Seek You Too B.V.) https://seecr.nl
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
from aiohttp.web import HTTPNotFound
from pathlib import Path
from urllib.parse import urlencode
from json import dumps, loads
from .template import Template
import sys

from importlib.util import spec_from_loader
from importlib.machinery import SourceFileLoader
import importlib


class TemplateImporter:
    """ finds modules in .sf files """
    def find_spec(self, qname, parent_path, target=None):
        parent_path = parent_path._path[0]
        name = qname.rsplit('.')[1]
        p = Path(parent_path) / f"{name}.sf"
        if p.is_file():
            s = spec_from_loader(qname, SourceFileLoader(qname, p.as_posix()))
            return s


class DynamicHtml:
    def __init__(self, modules):
        if len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]) == 0:
            sys.meta_path.append(TemplateImporter())

        self._watcher = aionotify.Watcher()
        self._modules = [modules] if not isinstance(modules, list) else modules
        for mod in self._modules:
            path = mod.__path__._path[0]
            self._watcher.watch(path, aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)

    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                modName = Path(event.alias).stem + "." + event.name[:-3]
                importlib.reload(sys.modules[modName])

    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())

    def render_page(self, name, request=None, response=None):
        template = self.templates[name]
        for each in template(request=request, response=response):
            yield each

    def handle_request(self, request, response):
        path = request.path
        if path[0] == '/':
            path = path[1:]
        path_parts = path.split("/", 1)
        if path_parts[0] in self.templates:
            return self.render_page(path_parts[0], request, response)
        raise HTTPNotFound()


from autotest import test


@test
def load_templates_on_create(tmp_path):
    (dyn_dir := tmp_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")
    sys.path.append(tmp_path.as_posix())

    import pruts
    DynamicHtml(pruts)
    from pruts import pruebo

    import inspect
    test.truth(inspect.isfunction(pruts.pruebo.main))


@test
def only_one_importer(tmp_path):
    (dyn_dir := tmp_path / "pruts").mkdir()
    (dyn_dir / "pruebo.sf").write_text("def main(**k): pass")
    sys.path.append(tmp_path.as_posix())

    import pruts
    DynamicHtml(pruts)
    currentCount = len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)])

    DynamicHtml(pruts)
    test.eq(currentCount, len([importer for importer in sys.meta_path if isinstance(importer, TemplateImporter)]))


@test
def multiple_modules_with_templates(tmp_path):
    for name in ['abra', 'cada', 'bra']:
        (dyn_dir := tmp_path / name).mkdir()
        (dyn_dir / "pruebo.sf").write_text(f"def main(**k): return '{name}'")

    sys.path.append(tmp_path.as_posix())

    import abra, cada, bra
    DynamicHtml([abra, cada, bra])
    from abra import pruebo
    test.eq("abra", pruebo.main())
    from cada import pruebo
    test.eq("cada", pruebo.main())


@test
async def reload_on_change(tmp_path):
    (dyn_dir := tmp_path / "pruts1").mkdir()
    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 1")
    sys.path.append(tmp_path.as_posix())

    import pruts1
    d = DynamicHtml(pruts1)
    d.run(asyncio.get_running_loop())
    await asyncio.sleep(0.1)

    import pruts1.pruebo1
    test.eq(1, pruts1.pruebo1.main())

    (dyn_dir / "pruebo1.sf").write_text("def main(**k): return 2 ")  # <-- essential space
    await asyncio.sleep(0.1)

    test.eq(2, pruts1.pruebo1.main())

