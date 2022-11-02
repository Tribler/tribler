import os
from unittest.mock import Mock, patch

import psutil
import pytest

from tribler.core.components.gui_process_watcher.gui_process_watcher import GUI_PID_ENV_KEY, GuiProcessNotRunning, \
    GuiProcessWatcher


@pytest.fixture(name='watcher')
async def watcher_fixture():
    gui_process = Mock()
    gui_process.is_running.return_value = True
    gui_process.status.return_value = psutil.STATUS_RUNNING
    shutdown_callback = Mock()
    watcher = GuiProcessWatcher(gui_process, shutdown_callback)
    watcher.start()
    yield watcher
    await watcher.stop()


def test_get_gui_pid(caplog):
    with patch.dict(os.environ, {GUI_PID_ENV_KEY: ''}):
        assert GuiProcessWatcher.get_gui_pid() is None

    with patch.dict(os.environ, {GUI_PID_ENV_KEY: 'abc'}):
        caplog.clear()
        assert GuiProcessWatcher.get_gui_pid() is None
        assert caplog.records[-1].message == 'Cannot parse TRIBLER_GUI_PID environment variable: abc'

    with patch.dict(os.environ, {GUI_PID_ENV_KEY: '123'}):
        assert GuiProcessWatcher.get_gui_pid() == 123


def test_get_gui_process():
    # pid is not specified
    with patch.dict(os.environ, {GUI_PID_ENV_KEY: ''}):
        assert GuiProcessWatcher.get_gui_process() is None

    pid = os.getpid()
    with patch.dict(os.environ, {GUI_PID_ENV_KEY: str(pid)}):
        # Process with the specified pid exists
        p = GuiProcessWatcher.get_gui_process()
        assert isinstance(p, psutil.Process)
        assert p.pid == pid

        # Process with the specified pid does not exist
        exception = psutil.NoSuchProcess(pid, name='name', msg='msg')
        with patch('psutil.Process', side_effect=exception):
            with pytest.raises(GuiProcessNotRunning):
                GuiProcessWatcher.get_gui_process()


def test_check_gui_process_working(watcher):
    watcher.check_gui_process()
    assert not watcher.shutdown_callback.called
    assert not watcher.shutdown_callback_called


def test_check_gui_process_zombie(watcher):
    watcher.gui_process.status.return_value = psutil.STATUS_ZOMBIE
    watcher.check_gui_process()
    assert watcher.shutdown_callback.called
    assert watcher.shutdown_callback_called


def test_check_gui_process_not_running(watcher):
    watcher.gui_process.is_running.return_value = False
    watcher.check_gui_process()
    assert not watcher.gui_process.status.called
    assert watcher.shutdown_callback.called
    assert watcher.shutdown_callback_called

    # Calling check_gui_process after shutdown_callback was already called
    watcher.shutdown_callback.reset_mock()
    watcher.check_gui_process()
    assert watcher.shutdown_callback_called
    assert not watcher.shutdown_callback.called
