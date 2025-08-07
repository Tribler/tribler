
import libtorrent
from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrentdef import TorrentDef
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
