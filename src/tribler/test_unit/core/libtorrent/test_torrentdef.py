from unittest.mock import AsyncMock, Mock, patch

import libtorrent
from aiohttp import ClientResponseError
from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS, TORRENT_WITH_DIRS_CONTENT, FakeTDef


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

    def test_create_invalid_tdef_empty_metainfo_validate(self) -> None:
        """
        Test if creating a TorrentDef object without metainfo and with validation results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef.load_from_dict({})

    def test_create_invalid_tdef_empty_info(self) -> None:
        """
        Test if creating a TorrentDef object with metainfo but an empty info dictionary results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef.load_from_dict({b"info": {}})

    def test_create_invalid_tdef_empty_info_validate(self) -> None:
        """
        Test if a TorrentDef object with metainfo but an empty info dict with validation results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef.load_from_dict({b"info": {}})

    def test_get_name_utf8(self) -> None:
        """
        Check if we can successfully get the UTF-8 encoded torrent name when using a different encoding.
        """
        tdef = FakeTDef(name="\xA1\xC0")

        self.assertEqual("\xa1\xc0", tdef.atp.name)

    async def test_load_from_url(self) -> None:
        """
        Test if torrents can be loaded from a URL.
        """
        response_mock = AsyncMock(read=AsyncMock(return_value=TORRENT_WITH_DIRS_CONTENT))
        with patch("aiohttp.ClientSession", Mock(return_value=Mock(
                get=AsyncMock(return_value=response_mock)))
        ):
            tdef = await TorrentDef.load_from_url("http://127.0.0.1:1234/ubuntu.torrent")

        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc", tdef.infohash)

    async def test_load_from_url_404(self) -> None:
        """
        Test if 404 errors are not caught.
        """
        with patch("aiohttp.ClientSession", Mock(return_value=Mock(
                get=AsyncMock(side_effect=ClientResponseError(None, None, status=404))))
        ), self.assertRaises(ClientResponseError):
            await TorrentDef.load_from_url("http://127.0.0.1:1234/ubuntu.torrent")

    def test_load_from_dict(self) -> None:
        """
        Test if a TorrentDef can be loaded from a dictionary.
        """
        metainfo = {b"info": libtorrent.bdecode(TORRENT_WITH_DIRS.metadata())}

        tdef = TorrentDef.load_from_dict(metainfo)

        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc", tdef.infohash)

    def test_get_name_as_unicode_path_utf8(self) -> None:
        """
        Test if names for files with a name.utf-8 path can be decoded.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef.load_from_dict({b"info": {b"name.utf-8": name_bytes,
                                                    b"files": [{b"path": [b"a.txt"], b"length": 123}],
                                                    b"piece length": 128, b"pieces": b"\x00" * 20}})

        self.assertEqual(name_unicode, tdef.name)

    def test_get_name_as_unicode(self) -> None:
        """
        Test if normal UTF-8 names can be decoded.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef.load_from_dict({b"info": {b"name": name_bytes,
                                                    b"files": [{b"path": [b"a.txt"], b"length": 123}],
                                                    b"piece length": 128, b"pieces": b"\x00" * 20}})

        self.assertEqual(name_unicode, tdef.name)
