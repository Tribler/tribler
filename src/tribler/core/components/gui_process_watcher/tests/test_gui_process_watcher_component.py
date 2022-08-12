import os
from unittest.mock import patch

import pytest

from tribler.core.components.base import Session
from tribler.core.components.gui_process_watcher.gui_process_watcher import GUI_PID_ENV_KEY
from tribler.core.components.gui_process_watcher.gui_process_watcher_component import GuiProcessWatcherComponent


@pytest.mark.asyncio
async def test_gui_process_watcher_component(tribler_config):
    with patch.dict(os.environ, {GUI_PID_ENV_KEY: str(os.getpid())}):
        components = [GuiProcessWatcherComponent()]
        async with Session(tribler_config, components).start():
            comp = GuiProcessWatcherComponent.instance()
            assert comp.started_event.is_set() and not comp.failed
            assert comp.watcher
