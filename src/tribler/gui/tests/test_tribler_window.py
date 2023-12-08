from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QFileDialog

from tribler.gui.tribler_window import TriblerWindow


# pylint: disable=redefined-outer-name
@pytest.fixture
def tribler_window():
    """ Create mocked TriblerWindow instance"""
    with patch('tribler.gui.tribler_window.TriblerWindow.__init__', Mock(return_value=None)):
        window = TriblerWindow(Mock(), Mock(), Mock(), Mock())
        window.pending_uri_requests = []
        return window


def test_on_add_torrent_browse_file(tribler_window: TriblerWindow):
    """ Test that the on_add_torrent_browse_file method works correctly"""
    tribler_window.raise_window = Mock()
    tribler_window.process_uri_request = Mock()

    with patch.object(QFileDialog, 'getOpenFileNames', Mock(return_value=['.'])) as patched_getOpenFileNames:
        tribler_window.on_add_torrent_browse_file()

    assert tribler_window.raise_window.called
    assert patched_getOpenFileNames.called
    assert tribler_window.process_uri_request.called
