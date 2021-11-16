from unittest.mock import MagicMock, patch

import pytest

from tribler_gui.core_manager import CoreCrashedError, CoreManager

pytestmark = pytest.mark.asyncio


# pylint: disable=
# fmt: off

@patch.object(CoreManager, 'on_finished')
@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
async def test_on_core_finished_call_on_finished(mocked_on_finished: MagicMock):
    # test that in case of `shutting_down` and `should_stop_on_shutdown` flags have been set to True
    # then `on_finished` function will be called and Exception will not be raised

    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock())
    core_manager.shutting_down = True
    core_manager.should_stop_on_shutdown = True

    core_manager.on_core_finished(exit_code=1, exit_status='exit status')
    mocked_on_finished.assert_called_once()


@patch('tribler_gui.core_manager.EventRequestManager', new=MagicMock())
async def test_on_core_finished_raises_error():
    # test that in case of flag `shutting_down` has been set to True and
    # exit_code is not equal to 0, then CoreRuntimeError should be raised

    core_manager = CoreManager(MagicMock(), MagicMock(), MagicMock())

    with pytest.raises(CoreCrashedError):
        core_manager.on_core_finished(exit_code=1, exit_status='exit status')
