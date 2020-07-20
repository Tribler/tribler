import json
import shutil
from binascii import unhexlify
from unittest.mock import Mock
from urllib.parse import quote_plus, unquote_plus

from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.restapi.base_api_test import do_request
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR, TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from tribler_core.utilities.path_util import pathname2url
from tribler_core.utilities.unicode import hexlify

SAMPLE_CHANNEL_FILES_DIR = TESTS_DIR / "data" / "sample_channel"


@pytest.mark.asyncio
async def test_get_torrentinfo(enable_chant, enable_api, mock_dlmgr, tmpdir, file_server, session):
    """
    Testing whether the API returns a correct dictionary with torrent info.
    """
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmpdir / 'ubuntu.torrent')

    def verify_valid_dict(json_data):
        metainfo_dict = json.loads(unhexlify(json_data['metainfo']), encoding='latin-1')
        # FIXME: This check is commented out because json.dump garbles pieces binary data during transfer.
        # To fix it, we must switch to some encoding scheme that is able to encode and decode raw binary
        # fields in the dicts.
        # However, for this works fine at the moment because we never use pieces data in the GUI.
        # assert TorrentDef.load_from_dict(metainfo_dict)
        assert 'info' in metainfo_dict

    session.dlmgr.downloads = {}
    session.dlmgr.metainfo_requests = {}
    session.dlmgr.get_channel_downloads = lambda: []
    session.dlmgr.shutdown = lambda: succeed(None)

    await do_request(session, 'torrentinfo', expected_code=400)
    await do_request(session, 'torrentinfo?uri=def', expected_code=400)

    path = "file:" + pathname2url(TESTS_DATA_DIR / "bak_single.torrent")
    verify_valid_dict(await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200))

    # Corrupt file
    path = "file:" + pathname2url(TESTS_DATA_DIR / "test_rss.xml")
    await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=500)

    # FIXME: !!! HTTP query for torrent produces dicts with unicode. TorrentDef creation can't handle unicode. !!!
    path = "http://localhost:%d/ubuntu.torrent" % file_server
    verify_valid_dict(await do_request(session, 'torrentinfo?uri=%s' % quote_plus(path), expected_code=200))

    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}'
                      f'&dn=test torrent&tr=http://ubuntu.org/ann')

    hops_list = []

    def get_metainfo(infohash, timeout=20, hops=None, url=None):
        if hops is not None:
            hops_list.append(hops)
        with open(TESTS_DATA_DIR / "ubuntu-15.04-desktop-amd64.iso.torrent", mode='rb') as torrent_file:
            torrent_data = torrent_file.read()
        tdef = TorrentDef.load_from_memory(torrent_data)
        assert url
        assert url == unquote_plus(path)
        return succeed(tdef.get_metainfo())

    session.dlmgr.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200))

    path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
    await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=400)

    path = quote_plus('magnet:?xt=urn:btih:%s&dn=%s' % ('a' * 40, 'test torrent'))
    session.dlmgr.get_metainfo = lambda *_, **__: succeed(None)
    await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=500)

    session.dlmgr.get_metainfo = get_metainfo
    verify_valid_dict(await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200))

    await do_request(session, 'torrentinfo?uri=%s&hops=0' % path, expected_code=200)
    assert [0] == hops_list

    await do_request(session, 'torrentinfo?uri=%s&hops=foo' % path, expected_code=400)

    path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
    await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=500)

    with db_session:
        assert session.mds.TorrentMetadata.select().count() == 2

    mock_download = Mock()
    path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn=test torrent')
    session.dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    result = await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200)
    assert result["download_exists"]

    # Check that we do not return "downloads_exists" if the download is metainfo only download
    session.dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    session.dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH: [mock_download]}
    result = await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200)
    assert not result["download_exists"]

    # Check that we return "downloads_exists" if there is a metainfo download for the infohash,
    # but there is also a regular download for the same infohash
    session.dlmgr.downloads = {UBUNTU_1504_INFOHASH: mock_download}
    session.dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH: [Mock()]}
    result = await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=200)
    assert result["download_exists"]


@pytest.mark.asyncio
async def test_on_got_invalid_metainfo(enable_api, mock_dlmgr, session):
    """
    Test whether the right operations happen when we receive an invalid metainfo object
    """
    def get_metainfo(*_, **__):
        return succeed("abcd")

    session.dlmgr.get_metainfo = get_metainfo
    session.dlmgr.shutdown = lambda: succeed(None)
    session.dlmgr.shutdown_downloads = lambda: succeed(None)
    session.dlmgr.checkpoint_downloads = lambda: succeed(None)
    path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))

    res = await do_request(session, 'torrentinfo?uri=%s' % path, expected_code=500)
    assert "error" in res
