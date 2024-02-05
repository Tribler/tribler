import shutil
from unittest.mock import Mock, patch

import pytest
from aiohttp import ClientResponseError

from tribler.core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import bdecode_compat

TRACKER = 'http://www.tribler.org/announce'
VIDEO_FILE_NAME = "video.avi"


def test_tdef_init():
    """
    Test initializing a TorrentDef object
    """
    tdef_params = TorrentDef(torrent_parameters={'announce': 'http://test.com'})
    assert 'announce' in tdef_params.torrent_parameters


def test_create_invalid_tdef():
    """
    Test whether creating invalid TorrentDef objects result in ValueErrors
    """
    invalid_metainfo = {}
    with pytest.raises(ValueError):
        TorrentDef(metainfo=invalid_metainfo)

    with pytest.raises(ValueError):
        TorrentDef(metainfo=invalid_metainfo, ignore_validation=False)

    invalid_metainfo = {b'info': {}}
    with pytest.raises(ValueError):
        TorrentDef(metainfo=invalid_metainfo)

    with pytest.raises(ValueError):
        TorrentDef(metainfo=invalid_metainfo, ignore_validation=False)


def test_add_content_dir(tdef):
    """
    Test whether adding a single content directory with two files is working correctly
    """
    torrent_dir = TESTS_DATA_DIR / "contentdir"
    tdef.add_content(torrent_dir / "file.txt")
    tdef.add_content(torrent_dir / "otherfile.txt")
    tdef.save()

    metainfo = tdef.get_metainfo()
    assert len(metainfo[b'info'][b'files']) == 2


def test_add_single_file(tdef):
    """
    Test whether adding a single file to a torrent is working correctly
    """
    torrent_dir = TESTS_DATA_DIR / "contentdir"
    tdef.add_content(torrent_dir / "file.txt")
    tdef.save()

    metainfo = tdef.get_metainfo()
    assert metainfo[b'info'][b'name'] == b'file.txt'


def test_get_name_utf8_unknown(tdef):
    """
    Test whether we can succesfully get the UTF-8 name
    """
    tdef.set_name(b'\xA1\xC0')
    tdef.torrent_parameters[b'encoding'] = 'euc_kr'
    assert tdef.get_name_utf8() == '\xf7'


def test_get_name_utf8(tdef):
    """
    Check whether we can successfully get the UTF-8 encoded torrent name when using a different encoding
    """
    tdef.set_name(b'\xA1\xC0')
    assert tdef.get_name_utf8() == '\xa1\xc0'


def test_add_content_piece_length(tdef):
    """
    Add a single file with piece length to a TorrentDef
    """
    fn = TESTS_DATA_DIR / VIDEO_FILE_NAME
    tdef.add_content(fn)
    tdef.set_piece_length(2 ** 16)
    tdef.save()

    metainfo = tdef.get_metainfo()
    assert metainfo[b'info'][b'piece length'] == 2 ** 16


def test_is_private(tdef):
    tdef.metainfo = {b'info': {b'private': 0}}
    assert tdef.is_private() is False

    tdef.metainfo = {b'info': {b'private': 1}}
    assert tdef.is_private() is True

    # There are torrents with the b"i1e" value of the `private` field. It looks like a double-encoded value 1:
    # first, the integer value 1 was encoded as a binary string b"i1e" and then encoded again as a part of the
    # "info" dictionary. In that case, we consider the attribute value invalid and treat it as a default value of 0
    tdef.metainfo = {b'info': {b'private': b'i1e'}}
    assert tdef.is_private() is False

    tdef.metainfo = {b'info': {b'private': b'i0e'}}
    assert tdef.is_private() is False


async def test_is_private_loaded_from_existing_torrent():
    """
    Test whether the private field from an existing torrent is correctly read
    """
    privatefn = TESTS_DATA_DIR / "private.torrent"
    publicfn = TESTS_DATA_DIR / "bak_single.torrent"

    t1 = await TorrentDef.load(privatefn)
    t2 = await TorrentDef.load(publicfn)

    assert t1.is_private()
    assert not t2.is_private()


async def test_load_from_url(file_server, tmpdir):
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmpdir / 'ubuntu.torrent')

    torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server
    torrent_def = await TorrentDef.load_from_url(torrent_url)
    assert torrent_def.get_metainfo() == (await TorrentDef.load(TORRENT_UBUNTU_FILE)).get_metainfo()
    assert torrent_def.infohash == (await TorrentDef.load(TORRENT_UBUNTU_FILE)).infohash


async def test_load_from_url_404(file_server, tmpdir):
    torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server
    try:
        await TorrentDef.load_from_url(torrent_url)
    except ClientResponseError as e:
        assert e.status == 404


def test_torrent_encoding(tdef):
    assert tdef.get_encoding() == "utf-8"
    tdef.set_encoding(b"my_fancy_encoding")
    assert tdef.get_encoding() == "my_fancy_encoding"


def test_set_tracker_invalid_url(tdef):
    with pytest.raises(ValueError):
        tdef.set_tracker("http/tracker.org")


def test_set_tracker_strip_slash(tdef):
    tdef.set_tracker("http://tracker.org/")
    assert tdef.torrent_parameters[b'announce'] == "http://tracker.org"


def test_set_tracker(tdef):
    assert len(tdef.get_trackers()) == 0
    tdef.set_tracker("http://tracker.org")
    assert tdef.get_trackers() == {'http://tracker.org'}


def test_get_trackers(tdef):
    """
    Test that `get_trackers` returns flat set of trackers
    """
    tdef.get_tracker_hierarchy = Mock(return_value=[["t1", "t2"], ["t3"], ["t4"]])
    trackers = tdef.get_trackers()
    assert trackers == {"t1", "t2", "t3", "t4"}


def test_get_nr_pieces(tdef):
    """
    Test getting the number of pieces from a TorrentDef
    """
    assert tdef.get_nr_pieces() == 0
    tdef.metainfo = {b'info': {b'pieces': b'a' * 40}}
    assert tdef.get_nr_pieces() == 2


def test_is_multifile(tdef):
    """
    Test whether a TorrentDef is correctly classified as multifile torrent
    """
    assert not tdef.is_multifile_torrent()

    tdef.metainfo = {}
    assert not tdef.is_multifile_torrent()

    tdef.metainfo = {b'info': {b'files': [b'a']}}
    assert tdef.is_multifile_torrent()


def test_set_piece_length_invalid_type(tdef):
    with pytest.raises(ValueError):
        tdef.set_piece_length("20")


def test_get_piece_length(tdef):
    assert tdef.get_piece_length() == 0


def test_load_from_dict():
    with open(TESTS_DATA_DIR / "bak_single.torrent", mode='rb') as torrent_file:
        encoded_metainfo = torrent_file.read()
    assert TorrentDef.load_from_dict(bdecode_compat(encoded_metainfo))


def test_torrent_no_metainfo():
    video_file_name_bytes = VIDEO_FILE_NAME.encode('utf-8')
    tdef = TorrentDefNoMetainfo(b"12345678901234567890", video_file_name_bytes, "http://google.com")
    assert tdef.get_name() == video_file_name_bytes
    assert tdef.get_infohash() == b"12345678901234567890"
    assert tdef.get_length() == 0  # there are no files
    assert not tdef.get_metainfo()
    assert tdef.get_url() == "http://google.com"
    assert not tdef.is_multifile_torrent()
    assert tdef.get_name_as_unicode() == VIDEO_FILE_NAME
    assert not tdef.get_files()
    assert tdef.get_files_with_length() == []
    assert len(tdef.get_trackers()) == 0
    assert not tdef.is_private()
    assert tdef.get_name_utf8() == VIDEO_FILE_NAME
    assert tdef.get_nr_pieces() == 0
    assert tdef.torrent_info is None
    tdef.load_torrent_info()
    assert tdef.torrent_info is None

    torrent2 = TorrentDefNoMetainfo(b"12345678901234567890", video_file_name_bytes, "magnet:")
    assert len(torrent2.get_trackers()) == 0


def test_get_infohash_hex_no_infohash(tdef: TorrentDef):
    # Test that get_infohash_hex returns None when there is no infohash
    assert not tdef.get_infohash_hex()


def test_get_infohash_hex(tdef: TorrentDef):
    # Test that get_infohash_hex returns the infohash in hex format
    tdef.infohash = b'0' * 20
    assert tdef.get_infohash_hex() == hexlify(tdef.infohash)


def test_get_infohash_hex_cached(tdef: TorrentDef):
    # Test that get_infohash_hex returns the infohash in hex format and caches the result
    tdef.infohash = b'0' * 20
    infohash_hex = hexlify(tdef.infohash)
    with patch('tribler.core.components.libtorrent.torrentdef.hexlify', Mock(side_effect=hexlify)) as mocked_hexlify:
        assert tdef.get_infohash_hex() == infohash_hex
        assert tdef.get_infohash_hex() == infohash_hex

        assert mocked_hexlify.call_count == 1


def test_get_length(tdef):
    """
    Test whether a TorrentDef has 0 length by default.
    """
    assert not tdef.get_length()


def test_get_index(tdef):
    """
    Test whether we can successfully get the index of a file in a torrent.
    """
    tdef.metainfo = {b'info': {b'files': [{b'path': [b'a.txt'], b'length': 123}]}}
    assert tdef.get_index_of_file_in_files('a.txt') == 0
    with pytest.raises(ValueError):
        tdef.get_index_of_file_in_files(b'b.txt')
    with pytest.raises(ValueError):
        tdef.get_index_of_file_in_files(None)

    tdef.metainfo = {b'info': {b'files': [{b'path': [b'a.txt'], b'path.utf-8': [b'b.txt'], b'length': 123}]}}
    assert tdef.get_index_of_file_in_files('b.txt') == 0

    tdef.metainfo = None
    with pytest.raises(ValueError):
        tdef.get_index_of_file_in_files('b.txt')


def test_get_name_as_unicode(tdef):
    name_bytes = b'\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86'
    name_unicode = name_bytes.decode()
    tdef.metainfo = {b'info': {b'name.utf-8': name_bytes}}
    assert tdef.get_name_as_unicode() == name_unicode
    tdef.metainfo = {b'info': {b'name': name_bytes}}
    assert tdef.get_name_as_unicode() == name_unicode
    tdef.metainfo = {b'info': {b'name': b'test\xff' + name_bytes}}
    assert tdef.get_name_as_unicode() == 'test' + '?' * len(b'\xff' + name_bytes)


def test_filter_characters(tdef):
    """
    Test `_filter_characters` sanitizes its input
    """
    name_bytes = b"\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86"
    name = name_bytes
    name_sanitized = "?" * len(name)
    assert tdef._filter_characters(name) == name_sanitized  # pylint: disable=protected-access
    name = b"test\xff" + name_bytes
    name_sanitized = "test" + "?" * len(b"\xff" + name_bytes)
    assert tdef._filter_characters(name) == name_sanitized  # pylint: disable=protected-access


def test_get_files_with_length(tdef):
    name_bytes = b'\xe8\xaf\xad\xe8\xa8\x80\xe5\xa4\x84\xe7\x90\x86'
    name_unicode = name_bytes.decode()
    tdef.metainfo = {b'info': {b'files': [{b'path.utf-8': [name_bytes], b'length': 123},
                                          {b'path.utf-8': [b'file.txt'], b'length': 456}]}}
    assert tdef.get_files_with_length() == [(Path(name_unicode), 123), (Path('file.txt'), 456)]

    tdef.metainfo = {b'info': {b'files': [{b'path': [name_bytes], b'length': 123},
                                          {b'path': [b'file.txt'], b'length': 456}]}}
    assert tdef.get_files_with_length() == [(Path(name_unicode), 123), (Path('file.txt'), 456)]

    tdef.metainfo = {b'info': {b'files': [{b'path': [b'test\xff' + name_bytes], b'length': 123},
                                          {b'path': [b'file.txt'], b'length': 456}]}}
    assert tdef.get_files_with_length() == [(Path('test?????????????'), 123), (Path('file.txt'), 456)]

    tdef.metainfo = {b'info': {b'files': [{b'path.utf-8': [b'test\xff' + name_bytes], b'length': 123},
                                          {b'path': [b'file.txt'], b'length': 456}]}}
    assert tdef.get_files_with_length() == [(Path('file.txt'), 456)]


def test_load_torrent_info(tdef: TorrentDef) -> None:
    """
    Test if load_torrent_info() loads the torrent info.
    """
    tdef.metainfo = {
        b'info': {
            b'name': 'torrent name',
            b'files': [{b'path': [b'a.txt'], b'length': 123}],
            b'piece length': 128,
            b'pieces': b'\x00' * 20
        }
    }

    assert not tdef.torrent_info_loaded()
    tdef.load_torrent_info()
    assert tdef.torrent_info_loaded()
    assert tdef.torrent_info is not None


def test_lazy_load_torrent_info(tdef: TorrentDef) -> None:
    """
    Test if accessing torrent_info loads the torrent info.
    """
    tdef.metainfo = {
        b'info': {
            b'name': 'torrent name',
            b'files': [{b'path': [b'a.txt'], b'length': 123}],
            b'piece length': 128,
            b'pieces': b'\x00' * 20
        }
    }

    assert not tdef.torrent_info_loaded()
    assert tdef.torrent_info is not None
    assert tdef.torrent_info_loaded()


def test_generate_tree(tdef: TorrentDef) -> None:
    """
    Test if a torrent tree can be generated from a TorrentDef.
    """
    tdef.metainfo = {
        b'info': {
            b'name': 'torrent name',
            b'files': [{b'path': [b'a.txt'], b'length': 123}],
            b'piece length': 128,
            b'pieces': b'\x00' * 20
        }
    }

    tree = tdef.torrent_file_tree

    assert tree.find(Path("torrent name") / "a.txt").size == 123
