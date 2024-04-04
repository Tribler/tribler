from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.database.orm_bindings.torrent_metadata import entries_to_chunk, infohash_to_id, tdef_to_metadata_dict
from tribler.core.libtorrent.torrentdef import TorrentDefNoMetainfo


class MockTorrentMetadata:
    """
    Mocked torrent metadata.
    """

    def __init__(self, start: int, stop: int) -> None:
        """
        Create mocked data and base its serialized form on the given range.
        """
        self.start = start
        self.stop = stop

    def serialized(self) -> bytes:
        """
        Serialize this mock to bytes.
        """
        return bytes(list(range(self.start, self.stop)))

    def serialized_health(self) -> bytes:
        """
        Serialize fake health to bytes.
        """
        return b"\x07"


class TestTorrentMetadata(TestBase):
    """
    Tests for the TorrentMetadata helpers.
    """

    def test_infohash_to_id(self) -> None:
        """
        Test if ids are calculated by the first 8 bytes of an infohash.
        """
        infohash1 = b"\x01" * 20
        infohash2 = b"\x01" * 8 + b"\x00" * 12
        infohash3 = b"\x01" * 7 + b"\x00" * 13

        self.assertEqual(72340172838076673, infohash_to_id(infohash1))
        self.assertEqual(72340172838076673, infohash_to_id(infohash2))
        self.assertEqual(72340172838076672, infohash_to_id(infohash3))

    def test_tdef_to_metadata_dict(self) -> None:
        """
        Test if TorrentDef instances are correctly represented by dictionaries.
        """
        tdef = TorrentDefNoMetainfo(b"\x01" * 20, b"torrent name", b"http://test.url/")

        value = tdef_to_metadata_dict(tdef)

        self.assertEqual(b"\x01" * 20, value["infohash"])
        self.assertEqual("torrent name", value["title"])
        self.assertEqual("Unknown", value["tags"])
        self.assertEqual(0, value["size"])
        self.assertEqual("", value["tracker_info"])

    def test_entries_to_chunk_last_index_no_fit(self) -> None:
        """
        Test if the last index of entries_to_chunk is correctly given if the data does not fit.
        """
        _, last_index = entries_to_chunk([MockTorrentMetadata(0, 99), MockTorrentMetadata(100, 199)], 1)

        self.assertEqual(1, last_index)

    def test_entries_to_chunk_last_index_fit(self) -> None:
        """
        Test if the last index of entries_to_chunk is correctly given if the data does fit.
        """
        _, last_index = entries_to_chunk([MockTorrentMetadata(0, 99), MockTorrentMetadata(100, 199)], 400)

        self.assertEqual(2, last_index)

    def test_entries_to_chunk_health(self) -> None:
        """
        Test if entries_to_chunk correctly gives the health data.
        """
        chunks, last_index = entries_to_chunk([MockTorrentMetadata(0, 99), MockTorrentMetadata(100, 199)], 1, 0, True)
        *_, health = chunks

        self.assertEqual(1, last_index)
        self.assertEqual(7, health)
