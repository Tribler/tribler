import shutil

from aiohttp import ClientResponseError

from libtorrent import bencode

import pytest

from tribler_core.components.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.utilities import bdecode_compat

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
        TorrentDef.load_from_memory(bencode(invalid_metainfo))

    invalid_metainfo = {b'info': {}}
    with pytest.raises(ValueError):
        TorrentDef.load_from_memory(bencode(invalid_metainfo))


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


def test_is_private():
    """
    Test whether the private field from an existing torrent is correctly read
    """
    privatefn = TESTS_DATA_DIR / "private.torrent"
    publicfn = TESTS_DATA_DIR / "bak_single.torrent"

    t1 = TorrentDef.load(privatefn)
    t2 = TorrentDef.load(publicfn)

    assert t1.is_private()
    assert not t2.is_private()


@pytest.mark.asyncio
async def test_load_from_url(file_server, tmpdir):
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmpdir / 'ubuntu.torrent')

    torrent_url = 'http://localhost:%d/ubuntu.torrent' % file_server
    torrent_def = await TorrentDef.load_from_url(torrent_url)
    assert torrent_def.get_metainfo() == TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
    assert torrent_def.infohash == TorrentDef.load(TORRENT_UBUNTU_FILE).infohash


@pytest.mark.asyncio
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
    assert not tdef.get_trackers_as_single_tuple()
    tdef.set_tracker("http://tracker.org")
    assert tdef.get_trackers_as_single_tuple() == ('http://tracker.org',)


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
    tdef = TorrentDefNoMetainfo(b"12345678901234567890", VIDEO_FILE_NAME, "http://google.com")
    assert tdef.get_name() == VIDEO_FILE_NAME
    assert tdef.get_infohash() == b"12345678901234567890"
    assert tdef.get_length() == 0  # there are no files
    assert not tdef.get_metainfo()
    assert tdef.get_url() == "http://google.com"
    assert not tdef.is_multifile_torrent()
    assert tdef.get_name_as_unicode() == VIDEO_FILE_NAME
    assert not tdef.get_files()
    assert tdef.get_files_with_length() == []
    assert not tdef.get_trackers_as_single_tuple()
    assert not tdef.is_private()
    assert tdef.get_name_utf8() == "video.avi"
    assert tdef.get_nr_pieces() == 0

    torrent2 = TorrentDefNoMetainfo(b"12345678901234567890", VIDEO_FILE_NAME, "magnet:")
    assert not torrent2.get_trackers_as_single_tuple()


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
    assert tdef.get_name_as_unicode() == 'test?????????????'


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
