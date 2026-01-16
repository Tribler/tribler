from unittest.mock import Mock

import libtorrent
from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrentdef import BLOCK_SIZE, TorrentDef
from tribler.test_unit.core.libtorrent.mocks import FakeTDef


class TestTorrentDef(TestBase):
    """
    Tests for the TorrentDef class.
    """

    def test_create_invalid_tdef_empty_metainfo(self) -> None:
        """
        Test if creating a TorrentDef object without metainfo results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef.load_from_memory(b"")

    def test_get_name_utf8(self) -> None:
        """
        Check if we can successfully get the UTF-8 encoded torrent name when using a different encoding.
        """
        tdef = FakeTDef(name="\xA1\xC0")

        self.assertEqual("\xa1\xc0", tdef.atp.name)

    def test_get_name_as_unicode(self) -> None:
        """
        Test if normal UTF-8 names can be decoded.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef.load_from_memory(libtorrent.bencode({
            b"info": {
                b"name": name_bytes,
                b"files": [{b"path": [b"a.txt"], b"length": 123}],
                b"piece length": 128, b"pieces": b"\x00" * 20
            }
        }))

        self.assertEqual(name_unicode, tdef.name)

    def test_get_file_indices_no_info(self) -> None:
        """
        Test if no files are returned when there is no torrent info.
        """
        tdef = TorrentDef(libtorrent.add_torrent_params())

        self.assertListEqual([], tdef.get_file_indices())

    def test_get_file_indices(self) -> None:
        """
        Test if files are returned as given by the torrent info.

        Note: The torrent_info bytes are generated using ``libtorrent.generate()``, which has the unfortunate tendency
              to segfault when called repeatedly while testing. The same holds for the following tests as well.
        """
        tdef = TorrentDef(libtorrent.add_torrent_params())
        tdef.atp.ti = libtorrent.torrent_info(
            b"d13:creation datei1759840893e4:infod5:filesl"
            b"d6:lengthi1e4:pathl5:a.txteed6:lengthi1e4:pathl5:b.txteee4:name4:test12:piece lengthi16384e"
            b"6:pieces20:\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01ee"
        )

        self.assertEqual(2, len(tdef.get_file_indices()))
        self.assertListEqual([0, 1], tdef.get_file_indices())

    def test_get_file_indices_exclude_pad(self) -> None:
        """
        Test if files do not return pad files.
        """
        tdef = TorrentDef(libtorrent.add_torrent_params())
        tdef.atp.ti = libtorrent.torrent_info(
            b"d13:creation datei1759840997e4:infod5:filesl"
            b"d6:lengthi1e4:pathl5:a.txteed4:attr1:p6:lengthi1e4:pathl5:b.txteee4:name4:test12:piece lengthi16384e"
            b"6:pieces20:\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01ee"
        )

        self.assertEqual(1, len(tdef.get_file_indices()))
        self.assertListEqual([0], tdef.get_file_indices())

    def test_get_file_indices_hidden(self) -> None:
        """
        Test if files with flags that are not padding files are still returned.
        """
        tdef = TorrentDef(libtorrent.add_torrent_params())
        tdef.atp.ti = libtorrent.torrent_info(
            b"d13:creation datei1759841092e4:infod5:filesl"
            b"d6:lengthi1e4:pathl5:a.txteed4:attr1:h6:lengthi1e4:pathl5:b.txteed4:attr1:x6:lengthi1e"
            b"4:pathl5:c.txteed6:lengthi1e4:pathl5:d.txteee4:name4:test12:piece lengthi16384e"
            b"6:pieces20:\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01ee"
        )

        self.assertEqual(4, len(tdef.get_file_indices()))
        self.assertListEqual([0, 1, 2, 3], tdef.get_file_indices())

    def test_get_v2_piece_indices_per_layer(self) -> None:
        """
        Test if the pieces are correctly returned for files.
        """
        tdef = TorrentDef(Mock())
        storage = libtorrent.file_storage()
        storage.set_piece_length(100)
        storage.set_num_pieces(3)
        storage.set_name("torrent name")
        # Case 1: file size > piece length, needs a root hash.
        storage.add_file("case 1", 123)  # Alignment 0: [ 100 bytes ],  1: [ 23 bytes | <padding> ]
        # Case 2: file size <= piece length, does not appear with a root hash.
        storage.add_file("case 2", 10)   # Alignment 2: [ 10 bytes | <padding> ]
        tdef.atp.ti = Mock(files=Mock(return_value=storage))

        self.assertDictEqual({b"\x00" * 32: [0, 1]}, tdef.get_v2_piece_indices_per_layer())

    def test_get_v2_piece_hash(self) -> None:
        """
        Test if the pieces are correctly returned for files.
        """
        tdef = TorrentDef(Mock())
        storage = libtorrent.file_storage()
        storage.set_piece_length(BLOCK_SIZE + 1)
        storage.set_num_pieces(2)
        storage.set_name("torrent name")
        # Piece alignment 0: [ BLOCK_SIZE+1 bytes ], 1: [ 22 bytes | <padding> ]
        # Block alignment 0: [ BLOCK_SIZE bytes ], 1: [ 1 byte ], 2: [ 22 bytes ], (<3>: [ BLOCK_SIZE bytes ])
        storage.add_file("file", BLOCK_SIZE + 23)
        tdef.atp.ti = Mock(files=Mock(return_value=storage))

        h0 = b"\x11\x1c\xe3\xc2\xa3\x8d\x83\xa2\xe4pk\xdeJ\xbd\xddP\x9d\x7f\x82H\x11lh2\xb0gE\xbd\xc3I\xe0\x9f"
        h1 = b"T6\x952\x0e^\xd1W\xaf\xaf\xdd\x9e?\x958<\x1a'\xc7\xd4hS\x7f\xa0#\x89\xcd\xaf'\xb7xX"

        self.assertEqual(h0, tdef.get_v2_piece_hash(0, b"\x01" * (BLOCK_SIZE + 1)))
        self.assertEqual(h1, tdef.get_v2_piece_hash(1, b"\x01" * 22 + b"\x00" * (BLOCK_SIZE + 1 - 22)))
        self.assertEqual(h1, tdef.get_v2_piece_hash(1, b"\x01" * (BLOCK_SIZE + 1)))
