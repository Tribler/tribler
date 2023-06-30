from unittest.mock import Mock

import pytest

from tribler.core.upgrade.version_manager import NoDiskSpaceAvailableError
from tribler.gui.upgrade_manager import StateDirUpgradeWorker, UpgradeManager


def test_state_dir_upgrader_when_no_disk_space_is_available():
    version_history = Mock()
    version_history.fork_state_directory_if_necessary = Mock(side_effect=NoDiskSpaceAvailableError(1, 2))

    worker = StateDirUpgradeWorker(version_history)
    worker.cancelled = Mock(emit=Mock())

    worker.run()

    worker.cancelled.emit.assert_called()


@pytest.mark.skip(reason="Flaky while running with test_gui.py")
def test_upgrader_when_no_disk_space_is_available(qtbot):
    version_history = Mock(last_run_version=None, get_disposable_versions=lambda _: [])
    version_history.fork_state_directory_if_necessary = Mock(side_effect=NoDiskSpaceAvailableError(1, 2))

    upgrade_manager = UpgradeManager(version_history)
    upgrade_manager.should_cleanup_old_versions = lambda: []
    upgrade_manager.quit_tribler_with_warning = Mock()

    with qtbot.waitSignal(upgrade_manager.upgrader_cancelled):
        upgrade_manager.start()

    upgrade_manager.quit_tribler_with_warning.assert_called()
