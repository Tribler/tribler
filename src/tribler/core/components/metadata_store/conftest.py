import pytest


# pylint: disable=redefined-outer-name

@pytest.fixture
def mock_dlmgr_get_download(mock_dlmgr):  # pylint: disable=unused-argument
    mock_dlmgr.get_download = lambda _: None
