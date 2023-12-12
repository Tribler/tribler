import pytest

from tribler.core.tests.tools.tracker.udp_tracker import UDPTracker


# pylint: disable=redefined-outer-name

@pytest.fixture
def mock_dlmgr_get_download(mock_dlmgr):  # pylint: disable=unused-argument
    mock_dlmgr.get_download = lambda _: None


@pytest.fixture
async def udp_tracker(free_port):
    udp_tracker = UDPTracker(free_port)
    yield udp_tracker
    await udp_tracker.stop()
