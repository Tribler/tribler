from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from tribler.core.components.database.db.serialization import TorrentMetadataPayload, UnknownBlobTypeException, \
    read_payload_with_offset


def test_fix_torrent_metadata_payload():
    """
    Check that TorrentMetadataPayload can handle both timestamps and datetime "torrent_date"s.
    """
    payload_1 = TorrentMetadataPayload(0, 0, bytes(range(64)), 0, 0, 0, bytes(range(20)), 0, 0,
                                       "title", "tags", "tracker_info")
    payload_2 = TorrentMetadataPayload(0, 0, bytes(range(64)), 0, 0, 0, bytes(range(20)), 0, datetime(1970, 1, 1),
                                       "title", "tags", "tracker_info")

    assert payload_1.serialized() == payload_2.serialized()


def test_torrent_metadata_payload_magnet():
    """
    Check that TorrentMetadataPayload produces an appropriate magnet link.
    """
    payload = TorrentMetadataPayload(0, 0, bytes(range(64)), 0, 0, 0, bytes(range(20)), 0, 0,
                                     "title", "tags", "tracker_info")
    expected = "magnet:?xt=urn:btih:000102030405060708090a0b0c0d0e0f10111213&dn=b'title'&tr=b'tracker_info'"

    assert expected == payload.get_magnet()


@patch('struct.unpack_from', Mock(return_value=(301,)))
def test_read_payload_with_offset_exception():
    # Test that an exception is raised when metadata_type != REGULAR_TORRENT
    with pytest.raises(UnknownBlobTypeException):
        read_payload_with_offset(b'')
