import asyncio
import aionotify


class DynamicHtml:
    def __init__(self, directories):
        self.directories = directories if isinstance(directories, list) else [directories]
        self.templates = {}
        self._load_templates()
        self._watcher = None
        self._init_inotify()

    def _init_inotify(self):
        self._watcher = aionotify.Watcher()
        for path in self.directories:
            self._watcher.watch(str(path), aionotify.Flags.MODIFY | aionotify.Flags.MOVED_TO)

    def _load_templates(self):
        for directory in self.directories:
            for path in directory.glob("*.sf"):
                self._load_template(path)

    def _load_template(self, filepath):
        module_globals = {}
        module_locals = {}
        with open(filepath, "rb") as f:
            exec(compile(f.read(), filepath, "exec"), module_globals, module_locals)
        self.templates[filepath.stem] = module_locals['main']

    async def _run(self):
        await self._watcher.setup(self.loop)
        while True:
            event = await self._watcher.get_event()
            if event.flags in [aionotify.Flags.MODIFY, aionotify.Flags.MOVED_TO] and event.name.endswith(".sf"):
                self._load_templates()

    def run(self, loop):
        self.loop = loop
        self.task = loop.create_task(self._run())


from autotest import test


@test
def create_ensures_directories_is_list(tmp_path):
    d = DynamicHtml(tmp_path)

    test.eq([tmp_path], d.directories)


@test
def load_templates_on_create(tmp_path):
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    d = DynamicHtml(tmp_path)
    test.eq(['pruebo'], list(d.templates.keys()))


@test
async def reload_templates_on_change(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)
    templates = str(d.templates['pruebo'])
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    await asyncio.sleep(.01)
    test.ne(templates, str(d.templates['pruebo']))

@test
async def reload_templates_on_create(tmp_path):
    loop = asyncio.get_running_loop()
    d = DynamicHtml(tmp_path)
    d.run(loop)
    await asyncio.sleep(.01)
    test.eq([], list(d.templates.keys()))
    (tmp_path / "pruebo.sf").write_text("def main(**k): pass")
    await asyncio.sleep(.01)
    test.eq(1, len(d.templates))
    test.eq(["pruebo"], list(d.templates.keys()))

@test
async def reload_templates_on_move(tmp_path):
    path_1 = tmp_path / "path_1"
    path_1.mkdir()
    path_2 = tmp_path / "path_2"
    path_2.mkdir()
    (path_2 / "pruebo.sf").write_text("def main(**k): pass")

    loop = asyncio.get_running_loop()
    d = DynamicHtml(path_1)
    d.run(loop)
    await asyncio.sleep(.01)
    test.eq([], list(d.templates.keys()))

    (path_2 / "pruebo.sf").rename(path_1 / "pruebo.sf")
    await asyncio.sleep(.01)
    test.eq(["pruebo"], list(d.templates.keys()))

@test
async def test_handle_request(tmp_path):
    loop = asyncio.get_running_loop()
    (tmp_path / "pruebo.sf").write_text("def main(**k): yield 'hello world'")
    d = DynamicHtml(tmp_path)
    d.run(loop)

    generator = d.handleRequest(request)



