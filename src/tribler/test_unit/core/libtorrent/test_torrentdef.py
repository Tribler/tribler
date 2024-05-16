from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import libtorrent
from aiohttp import ClientResponseError
from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS, TORRENT_WITH_DIRS_CONTENT


class TestTorrentDef(TestBase):
    """
    Tests for the TorrentDef class.
    """

    def test_tdef_init_parameters(self) -> None:
        """
        Test if a TorrentDef object can be initialized with parameters.
        """
        tdef_params = TorrentDef(torrent_parameters={b"announce": "http://test.com"})

        self.assertIn(b"announce", tdef_params.torrent_parameters)

    def test_create_invalid_tdef_empty_metainfo(self) -> None:
        """
        Test if creating a TorrentDef object without metainfo results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef(metainfo={})

    def test_create_invalid_tdef_empty_metainfo_validate(self) -> None:
        """
        Test if creating a TorrentDef object without metainfo and with validation results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef(metainfo={}, ignore_validation=False)

    def test_create_invalid_tdef_empty_info(self) -> None:
        """
        Test if creating a TorrentDef object with metainfo but an empty info dictionary results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef(metainfo={b"info": {}})

    def test_create_invalid_tdef_empty_info_validate(self) -> None:
        """
        Test if a TorrentDef object with metainfo but an empty info dict with validation results in a ValueError.
        """
        with self.assertRaises(ValueError):
            TorrentDef(metainfo={b"info": {}}, ignore_validation=False)

    def test_get_name_utf8_unknown(self) -> None:
        """
        Test if we can succesfully get the UTF-8 name.
        """
        tdef = TorrentDef()

        tdef.set_name(b"\xA1\xC0")
        tdef.torrent_parameters[b"encoding"] = b"euc_kr"

        self.assertEqual("\xf7", tdef.get_name_utf8())

    def test_get_name_utf8(self) -> None:
        """
        Check if we can successfully get the UTF-8 encoded torrent name when using a different encoding.
        """
        tdef = TorrentDef()

        tdef.set_name(b"\xA1\xC0")

        self.assertEqual("\xa1\xc0", tdef.get_name_utf8())

    def test_is_private_non_private(self) -> None:
        """
        Test if a torrent marked with private = 0 is not seen as private.
        """
        tdef = TorrentDef()

        tdef.metainfo = {b"info": {b"private": 0}}

        self.assertFalse(tdef.is_private())

    def test_is_private_private(self) -> None:
        """
        Test if a torrent marked with private = 1 is seen as private.
        """
        tdef = TorrentDef()

        tdef.metainfo = {b"info": {b"private": 1}}

        self.assertTrue(tdef.is_private())

    def test_is_private_i1e(self) -> None:
        """
        Test if an invalid but common private field setting of i1e (instead of 1) is not valid as private.
        """
        tdef = TorrentDef()

        tdef.metainfo = {b"info": {b"private": b"i1e"}}

        self.assertFalse(tdef.is_private())

    def test_is_private_i0e(self) -> None:
        """
        Test if an invalid but common private field setting of i0e (instead of 0) is not valid as private.
        """
        tdef = TorrentDef()

        tdef.metainfo = {b"info": {b"private": b"i0e"}}

        self.assertFalse(tdef.is_private())

    def test_load_private_from_memory_nothing(self) -> None:
        """
        Test if loading the private field set to nothing from an existing torrent works correctly.
        """
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)

        self.assertFalse(tdef.is_private())

    def test_load_private_from_memory_public(self) -> None:
        """
        Test if loading the private field set to 0 from an existing torrent works correctly.
        """
        info_dict_index = TORRENT_WITH_DIRS_CONTENT.find(b"4:infod") + 7
        new_content = (TORRENT_WITH_DIRS_CONTENT[:info_dict_index]
                       + b"7:privatei0e"
                       + TORRENT_WITH_DIRS_CONTENT[info_dict_index:])
        tdef = TorrentDef.load_from_memory(new_content)

        self.assertFalse(tdef.is_private())

    def test_load_private_from_memory_private(self) -> None:
        """
        Test if loading the private field set to 1 from an existing torrent works correctly.
        """
        info_dict_index = TORRENT_WITH_DIRS_CONTENT.find(b"4:infod") + 7
        new_content = (TORRENT_WITH_DIRS_CONTENT[:info_dict_index]
                       + b"7:privatei1e"
                       + TORRENT_WITH_DIRS_CONTENT[info_dict_index:])
        tdef = TorrentDef.load_from_memory(new_content)

        self.assertTrue(tdef.is_private())

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

    def test_torrent_default_encoding(self) -> None:
        """
        Test if the default encoding is set to UTF-8.
        """
        tdef = TorrentDef()

        self.assertEqual("utf-8", tdef.get_encoding())

    def test_torrent_encoding(self) -> None:
        """
        Test if the encoding can be set to any string.
        """
        tdef = TorrentDef()

        tdef.set_encoding(b"my_fancy_encoding")

        self.assertEqual("my_fancy_encoding", tdef.get_encoding())

    def test_set_tracker_invalid_url(self) -> None:
        """
        Test if setting an invalid tracker raises a ValueError.
        """
        tdef = TorrentDef()

        with self.assertRaises(ValueError):
            tdef.set_tracker("http/tracker.org")

    def test_set_tracker_strip_slash(self) -> None:
        """
        Test if the final slash in a tracker URL is stripped.
        """
        tdef = TorrentDef()

        tdef.set_tracker("http://tracker.org/")

        self.assertEqual("http://tracker.org", tdef.torrent_parameters[b"announce"])

    def test_set_tracker(self) -> None:
        """
        Test if a tracker can be set to a valid URL.
        """
        tdef = TorrentDef()

        tdef.set_tracker("http://tracker.org")

        self.assertSetEqual({'http://tracker.org'},  tdef.get_trackers())

    def test_get_trackers(self) -> None:
        """
        Test if get_trackers returns flat set of trackers.
        """
        tdef = TorrentDef()
        tdef.get_tracker_hierarchy = Mock(return_value=[["t1", "t2"], ["t3"], ["t4"]])

        trackers = tdef.get_trackers()

        self.assertSetEqual({"t1", "t2", "t3", "t4"}, trackers)

    def test_get_default_nr_pieces(self) -> None:
        """
        Test if the default number of pieces is zero.
        """
        tdef = TorrentDef()

        self.assertEqual(0, tdef.get_nr_pieces())

    def test_get_nr_pieces(self) -> None:
        """
        Test if the number of pieces can be retrieved from a TorrentDef.
        """
        tdef = TorrentDef()

        tdef.metainfo = {b"info": {b"pieces": b"a" * 40}}

        self.assertEqual(2, tdef.get_nr_pieces())

    def test_is_multifile_empty(self) -> None:
        """
        Test if an empty TorrentDef is not classified as a multifile torrent.
        """
        tdef = TorrentDef()

        self.assertFalse(tdef.is_multifile_torrent())

    def test_is_multifile(self) -> None:
        """
        Test if a TorrentDef is correctly classified as multifile torrent.
        """
        tdef = TorrentDef(metainfo={b"info": {b"files": [b"a"]}})

        self.assertTrue(tdef.is_multifile_torrent())

    def test_set_piece_length_invalid_type(self) -> None:
        """
        Test if the piece length cannot be set to something other than an int.
        """
        tdef = TorrentDef()

        with self.assertRaises(ValueError):
            tdef.set_piece_length(b"20")

    def test_get_piece_length(self) -> None:
        """
        Test if the default piece length is zero.
        """
        tdef = TorrentDef()

        self.assertEqual(0, tdef.get_piece_length())

    def test_load_from_dict(self) -> None:
        """
        Test if a TorrentDef can be loaded from a dictionary.
        """
        metainfo = {b"info": libtorrent.bdecode(TORRENT_WITH_DIRS.metadata())}

        tdef = TorrentDef.load_from_dict(metainfo)

        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc", tdef.infohash)

    def test_torrent_no_metainfo(self) -> None:
        """
        Test if a TorrentDefNoMetainfo can be constructed from torrent file information.
        """
        tdef = TorrentDefNoMetainfo(b"12345678901234567890", b"ubuntu.torrent", "http://google.com")

        self.assertEqual(b"ubuntu.torrent", tdef.get_name())
        self.assertEqual(b"12345678901234567890", tdef.get_infohash())
        self.assertEqual(0, tdef.get_length())
        self.assertIsNone(tdef.get_metainfo())
        self.assertEqual(b"http://google.com", tdef.get_url())
        self.assertFalse(tdef.is_multifile_torrent())
        self.assertEqual("ubuntu.torrent", tdef.get_name_as_unicode())
        self.assertEqual([], tdef.get_files())
        self.assertEqual([], tdef.get_files_with_length())
        self.assertEqual(0, len(tdef.get_trackers()))
        self.assertFalse(tdef.is_private())
        self.assertEqual("ubuntu.torrent", tdef.get_name_utf8())
        self.assertEqual(0, tdef.get_nr_pieces())
        self.assertIsNone(tdef.torrent_info)

    def test_torrent_no_metainfo_load_info(self) -> None:
        """
        Test if a TorrentDefNoMetainfo does not load torrent info if there is none to load by definition.
        """
        tdef = TorrentDefNoMetainfo(b"12345678901234567890", b"ubuntu.torrent", "http://google.com")

        tdef.load_torrent_info()

        self.assertIsNone(tdef.torrent_info)

    def test_magnet_no_metainfo(self) -> None:
        """
        Test if a TorrentDefNoMetainfo can be constructed from magnet link information.
        """
        torrent2 = TorrentDefNoMetainfo(b"12345678901234567890", b"ubuntu.torrent", "magnet:")

        self.assertEqual(0, len(torrent2.get_trackers()))

    def test_get_length(self) -> None:
        """
        Test if a TorrentDef has 0 length by default.
        """
        tdef = TorrentDef()

        self.assertEqual(0, tdef.get_length())

    def test_get_index(self) -> None:
        """
        Test if we can successfully get the index of a file in a torrent.
        """
        tdef = TorrentDef(metainfo={b"info": {b"files": [{b"path": [b"a.txt"], b"length": 123}]}})

        self.assertEqual(0, tdef.get_index_of_file_in_files("a.txt"))
        with self.assertRaises(ValueError):
            tdef.get_index_of_file_in_files("b.txt")
        with self.assertRaises(ValueError):
            tdef.get_index_of_file_in_files(None)

    def test_get_index_utf8(self) -> None:
        """
        Test if we can successfully get the index of a path.utf-8 file in a torrent.
        """
        tdef = TorrentDef({b"info": {b"files": [{b"path": [b"a.txt"], b"path.utf-8": [b"b.txt"], b"length": 123}]}})

        self.assertEqual(0, tdef.get_index_of_file_in_files("b.txt"))

    def test_get_index_no_metainfo(self) -> None:
        """
        Test if attempting to fetch a file from a TorrentDef without metainfo results in a ValueError.
        """
        tdef = TorrentDef(metainfo=None)

        with self.assertRaises(ValueError):
            tdef.get_index_of_file_in_files("b.txt")

    def test_get_name_as_unicode_path_utf8(self) -> None:
        """
        Test if names for files with a name.utf-8 path can be decoded.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef(metainfo={b"info": {b"name.utf-8": name_bytes}})

        self.assertEqual(name_unicode, tdef.get_name_as_unicode())

    def test_get_name_as_unicode(self) -> None:
        """
        Test if normal UTF-8 names can be decoded.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef(metainfo={b"info": {b"name": name_bytes}})

        self.assertEqual(name_unicode, tdef.get_name_as_unicode())

    def test_get_name_as_unicode_replace_illegal(self) -> None:
        """
        Test if illegal characters are replaced with question marks.

        Note: the FF byte ruins the unicode encoding for all following bytes.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        tdef = TorrentDef(metainfo={b"info": {b"name": b"test\xff" + name_bytes}})

        self.assertEqual("test" + "?" * len(b"\xff" + name_bytes),  tdef.get_name_as_unicode())

    def test_get_files_with_length(self) -> None:
        """
        Test if get_files_with_length returns the correct result for normal path names.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef(metainfo={b"info": {b"files": [{b"path.utf-8": [name_bytes], b"length": 123},
                                                         {b"path.utf-8": [b"file.txt"], b"length": 456}]}})

        self.assertEqual([(Path(name_unicode), 123), (Path('file.txt'), 456)], tdef.get_files_with_length())

    def test_get_files_with_length_valid_path_utf8(self) -> None:
        """
        Test if get_files_with_length returns the correct result for path.utf-8 names.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        name_unicode = name_bytes.decode()
        tdef = TorrentDef(metainfo={b"info": {b"files": [{b"path": [name_bytes], b"length": 123},
                                                         {b"path": [b"file.txt"], b"length": 456}]}})

        self.assertEqual([(Path(name_unicode), 123), (Path('file.txt'), 456)], tdef.get_files_with_length())

    def test_get_files_with_length_illegal_path(self) -> None:
        """
        Test if get_files_with_length sanitizes files with invalid path names.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        tdef = TorrentDef(metainfo={b"info": {b"files": [{b"path": [b"test\xff" + name_bytes], b"length": 123},
                                                         {b"path": [b"file.txt"], b"length": 456}]}})

        self.assertEqual([(Path("test?????????????"), 123), (Path("file.txt"), 456)], tdef.get_files_with_length())

    def test_get_files_with_length_illegal_path_utf8(self) -> None:
        """
        Test if get_files_with_length sanitizes files with invalid path.utf-8 names.
        """
        name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
        tdef = TorrentDef(metainfo={b"info": {b"files": [{b"path.utf-8": [b"test\xff" + name_bytes], b"length": 123},
                                                         {b"path": [b"file.txt"], b"length": 456}]}})

        self.assertEqual([(Path("file.txt"), 456)], tdef.get_files_with_length())

    def test_load_torrent_info(self) -> None:
        """
        Test if load_torrent_info() loads the torrent info.
        """
        tdef = TorrentDef(metainfo={
            b"info": {
                b"name": b"torrent name",
                b"files": [{b"path": [b"a.txt"], b"length": 123}],
                b"piece length": 128,
                b"pieces": b"\x00" * 20
            }
        })

        tdef.load_torrent_info()

        self.assertTrue(tdef.torrent_info_loaded())
        self.assertIsNotNone(tdef.torrent_info)

    def test_lazy_load_torrent_info(self) -> None:
        """
        Test if accessing torrent_info loads the torrent info.
        """
        tdef = TorrentDef(metainfo={
            b"info": {
                b"name": b"torrent name",
                b"files": [{b"path": [b"a.txt"], b"length": 123}],
                b"piece length": 128,
                b"pieces": b"\x00" * 20
            }
        })

        self.assertFalse(tdef.torrent_info_loaded())
        self.assertIsNotNone(tdef.torrent_info)
        self.assertTrue(tdef.torrent_info_loaded())

    def test_generate_tree(self) -> None:
        """
        Test if a torrent tree can be generated from a TorrentDef.
        """
        tdef = TorrentDef(metainfo={
            b"info": {
                b"name": b"torrent name",
                b"files": [{b"path": [b"a.txt"], b"length": 123}],
                b"piece length": 128,
                b"pieces": b"\x00" * 20
            }
        })

        tree = tdef.torrent_file_tree

        self.assertEqual(123, tree.find(Path("torrent name") / "a.txt").size)
