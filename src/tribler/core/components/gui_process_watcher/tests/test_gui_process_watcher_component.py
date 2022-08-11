import os
from unittest.mock import patch

from tribler.core.components.gui_process_watcher.gui_process_watcher import GUI_PID_ENV_KEY
from tribler.core.components.gui_process_watcher.gui_process_watcher_component import GuiProcessWatcherComponent
from tribler.core.components.session import Session


async def test_watch_folder_component(tribler_config):
    with patch.dict(os.environ, {GUI_PID_ENV_KEY: str(os.getpid())}):
        components = [GuiProcessWatcherComponent()]
        async with Session(tribler_config, components) as session:
            comp = session.get_instance(GuiProcessWatcherComponent)
            assert comp.started_event.is_set() and not comp.failed
            assert comp.watcher
