import os
from binascii import unhexlify
from unittest.mock import Mock

from ipv8.util import fail, succeed

from pony.orm import db_session

import pytest

from tribler_core.modules.libtorrent.download_state import DownloadState
from tribler_core.restapi.base_api_test import do_request
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TESTS_DIR
from tribler_core.utilities.unicode import hexlify


def get_hex_infohash(tdef):
    return hexlify(tdef.get_infohash())


@pytest.mark.asyncio
async def test_get_downloads_no_downloads(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns an empty list when downloads are fetched but no downloads are active
    """
    result = await do_request(session, 'downloads?get_peers=1&get_pieces=1',
                              expected_code=200, expected_json={"downloads": []})
    assert result["downloads"] == []


@pytest.mark.asyncio
async def test_get_downloads(enable_chant, enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns the right download when a download is added
    """
    session.dlmgr.get_downloads = lambda: [test_download]
    downloads = await do_request(session, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert len(downloads["downloads"]) == 1


@pytest.mark.asyncio
async def test_start_download_no_uri(enable_api, session):
    """
    Testing whether an error is returned when we start a torrent download and do not pass any URI
    """
    await do_request(session, 'downloads', expected_code=400, request_type='PUT')


@pytest.mark.asyncio
async def test_start_download_bad_params(enable_api, session):
    """
    Testing whether an error is returned when we start a torrent download and pass wrong data
    """
    post_data = {'anon_hops': 1, 'safe_seeding': 0, 'uri': 'abcd'}
    await do_request(session, 'downloads', expected_code=400, request_type='PUT', post_data=post_data)


@pytest.mark.asyncio
async def test_start_download_from_file(enable_api, test_download, mock_dlmgr, session):
    """
    Testing whether we can start a download from a file
    """
    session.dlmgr.start_download_from_uri = lambda *_, **__: succeed(test_download)

    post_data = {'uri': 'file:%s' % (TESTS_DATA_DIR / 'video.avi.torrent')}
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(session, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)


@pytest.mark.asyncio
async def test_start_download_with_selected_files(enable_api, test_download, mock_dlmgr, session):
    """
    Testing whether we can start a download with the selected_files parameter set
    """
    def mocked_start_download(*_, config=None):
        assert config.get_selected_files() == [0]
        return succeed(test_download)

    session.dlmgr.start_download_from_uri = mocked_start_download

    post_data = {'uri': 'file:%s' % (TESTS_DATA_DIR / 'video.avi.torrent'), 'selected_files': [0]}
    expected_json = {'started': True, 'infohash': 'c9a19e7fe5d9a6c106d6ea3c01746ac88ca3c7a5'}
    await do_request(session, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)


@pytest.mark.asyncio
async def test_get_peers_illegal_fields_ascii(enable_chant, enable_api, test_download, mock_dlmgr, mock_lt_status,
                                              session):
    """
    Testing whether illegal fields are stripped from the Libtorrent download info response.
    """
    session.dlmgr.get_downloads = lambda: [test_download]

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': 'uTorrent 1.6.1'}]
    test_download.get_state = lambda: ds

    response_dict = await do_request(session, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert "downloads" in response_dict
    assert len(response_dict["downloads"]) == 1
    assert "peers" in response_dict["downloads"][0]
    assert len(response_dict["downloads"][0]["peers"]) == 1
    assert 'have' not in response_dict["downloads"][0]["peers"][0]
    assert response_dict["downloads"][0]["peers"][0]['extended_version'] == 'uTorrent 1.6.1'


@pytest.mark.asyncio
async def test_get_peers_illegal_fields_unknown(enable_chant, enable_api, test_download, mock_dlmgr, mock_lt_status,
                                                session):
    """
    Testing whether illegal fields are stripped from the Libtorrent download info response.
    """
    session.dlmgr.get_downloads = lambda: [test_download]

    ds = DownloadState(test_download, mock_lt_status, None)
    ds.get_peerlist = lambda: [{'id': '1234', 'have': '5678', 'extended_version': None}]
    test_download.get_state = lambda: ds

    response_dict = await do_request(session, 'downloads?get_peers=1&get_pieces=1', expected_code=200)
    assert response_dict["downloads"][0]["peers"][0]['extended_version'] == ''


@pytest.mark.asyncio
async def test_start_invalid_download(enable_api, mock_dlmgr, session):
    """
    Testing whether an Exception triggered in start_download_from_uri is correctly handled
    """
    def mocked_start_download(*_, **__):
        raise Exception("test")

    session.dlmgr.start_download_from_uri = mocked_start_download

    post_data = {'uri': 'http://localhost:1234/test.torrent'}
    result = await do_request(session, 'downloads', expected_code=500, request_type='PUT', post_data=post_data)
    assert result["error"] == "test"


@pytest.mark.asyncio
async def test_remove_no_remove_data_param(enable_api, session):
    """
    Testing whether the API returns error 400 if the remove_data parameter is not passed
    """
    await do_request(session, 'downloads/abcd', expected_code=400, request_type='DELETE')


@pytest.mark.asyncio
async def test_remove_wrong_infohash(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if a non-existent download is removed
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, 'downloads/abcd', post_data={"remove_data": True},
                     expected_code=404, request_type='DELETE')


@pytest.mark.asyncio
async def test_remove(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 200 if a download is being removed
    """
    session.dlmgr.get_download = lambda _: test_download
    session.dlmgr.remove_download = lambda *_, **__: succeed(None)

    await do_request(session, 'downloads/%s' % test_download.infohash, post_data={"remove_data": False},
                     expected_code=200, request_type='DELETE',
                     expected_json={"removed": True, "infohash": test_download.infohash})


@pytest.mark.asyncio
async def test_stop_download_wrong_infohash(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if a non-existent download is stopped
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, 'downloads/abcd', expected_code=404, post_data={"state": "stop"}, request_type='PATCH')


@pytest.mark.asyncio
async def test_stop_download(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 200 if a download is being stopped
    """
    session.dlmgr.get_download = lambda _: test_download

    def mocked_stop(*_, **__):
        test_download.should_stop = True
        return succeed(None)
    test_download.stop = mocked_stop

    await do_request(session, f'downloads/{test_download.infohash}', post_data={"state": "stop"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    assert test_download.should_stop


@pytest.mark.asyncio
async def test_select_download_file_range(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether an error is returned when we toggle a file for inclusion out of range
    """
    session.dlmgr.get_download = lambda _: test_download

    await do_request(session, f'downloads/{test_download.infohash}', expected_code=400,
                     post_data={"selected_files": [1234]}, request_type='PATCH')


@pytest.mark.asyncio
async def test_select_download_file(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether files can be correctly toggled in a download
    """
    session.dlmgr.get_download = lambda _: test_download
    test_download.set_selected_files = Mock()

    await do_request(session, f'downloads/{test_download.infohash}', post_data={"selected_files": [0]},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    test_download.set_selected_files.assert_called_with([0])


@pytest.mark.asyncio
async def test_load_checkpoint_wrong_infohash(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if a non-existent download is resumed
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, 'downloads/abcd', expected_code=404, post_data={"state": "resume"}, request_type='PATCH')


@pytest.mark.asyncio
async def test_resume_download(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 200 if a download is being resumed
    """
    session.dlmgr.get_download = lambda _: test_download

    def mocked_resume():
        test_download.should_resume = True
    test_download.resume = mocked_resume

    await do_request(session, f'downloads/{test_download.infohash}', post_data={"state": "resume"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    assert test_download.should_resume


@pytest.mark.asyncio
async def test_recheck_download(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 200 if a download is being rechecked
    """
    session.dlmgr.get_download = lambda _: test_download
    test_download.force_recheck = Mock()

    await do_request(session, 'downloads/%s' % test_download.infohash, post_data={"state": "recheck"},
                     expected_code=200, request_type='PATCH',
                     expected_json={"modified": True, "infohash": test_download.infohash})
    test_download.force_recheck.assert_called_once()


@pytest.mark.asyncio
async def test_download_unknown_state(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns error 400 if an unknown state is passed when modifying a download
    """
    session.dlmgr.get_download = lambda _: test_download

    await do_request(session, 'downloads/%s' % test_download.infohash, expected_code=400,
                     post_data={"state": "abc"}, request_type='PATCH',
                     expected_json={"error": "unknown state parameter"})


@pytest.mark.asyncio
async def test_change_hops_error(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 400 if we supply both anon_hops and another parameter
    """
    session.dlmgr.get_download = lambda _: True
    await do_request(session, 'downloads/%s' % test_download.infohash, post_data={"state": "resume", 'anon_hops': 1},
                     expected_code=400, request_type='PATCH')


@pytest.mark.asyncio
async def test_move_to_non_existing_dir(enable_api, mock_dlmgr, test_download, session, tmpdir):
    """
    Testing whether moving the torrent storage to a non-existing directory works as expected.
    """
    session.dlmgr.get_download = lambda _: test_download

    dest_dir = tmpdir / "non-existing"
    assert not dest_dir.exists()
    data = {"state": "move_storage", "dest_dir": str(dest_dir)}

    response_dict = await do_request(session, 'downloads/%s' % test_download.infohash,
                                     expected_code=200, post_data=data, request_type='PATCH')
    assert "error" in response_dict
    assert "Target directory (%s) does not exist" % dest_dir == response_dict["error"]


@pytest.mark.asyncio
async def test_move_to_existing_dir(enable_api, mock_dlmgr, test_download, session, tmpdir):
    """
    Testing whether moving the torrent storage to an existing directory works as expected.
    """
    session.dlmgr.get_download = lambda _: test_download

    dest_dir = tmpdir / "existing"
    os.mkdir(dest_dir)
    data = {"state": "move_storage", "dest_dir": str(dest_dir)}

    response_dict = await do_request(session, 'downloads/%s' % test_download.infohash,
                                     expected_code=200, post_data=data, request_type='PATCH')
    assert response_dict.get("modified", False)
    assert test_download.infohash == response_dict["infohash"]


@pytest.mark.asyncio
async def test_export_unknown_download(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if a non-existent download is exported
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, 'downloads/abcd/torrent', expected_code=404, request_type='GET')


@pytest.mark.asyncio
async def test_export_download(enable_api, mock_dlmgr, mock_handle, test_download, session):
    """
    Testing whether the API returns the contents of the torrent file if a download is exported
    """
    test_download.get_torrent_data = lambda: 'a' * 20
    session.dlmgr.get_download = lambda _: test_download
    await do_request(session, 'downloads/%s/torrent' % test_download.infohash,
                     expected_code=200, request_type='GET', json_response=False)


@pytest.mark.asyncio
async def test_get_files_unknown_download(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if the files of a non-existent download are requested
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, 'downloads/abcd/files', expected_code=404, request_type='GET')


@pytest.mark.asyncio
async def test_get_download_files(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns file information of a specific download when requested
    """
    session.dlmgr.get_download = lambda _: test_download

    response_dict = await do_request(session, 'downloads/%s/files' % test_download.infohash,
                                     expected_code=200, request_type='GET')
    assert 'files' in response_dict
    assert response_dict['files']


@pytest.mark.asyncio
async def test_stream_unknown_download(enable_api, mock_dlmgr, session):
    """
    Testing whether the API returns error 404 if we stream a non-existent download
    """
    session.dlmgr.get_download = lambda _: None
    await do_request(session, f'downloads/abcd/stream/0',
                     headers={'range': 'bytes=0-'}, expected_code=404, request_type='GET')


@pytest.mark.asyncio
async def test_stream_download_out_of_bounds_file(enable_api, mock_dlmgr, mock_handle, test_download, session):
    """
    Testing whether the API returns code 404 if we stream with a file index out of bounds
    """
    session.dlmgr.get_download = lambda _: test_download
    await do_request(session, f'downloads/{test_download.infohash}/stream/100',
                     headers={'range': 'bytes=0-'}, expected_code=500, request_type='GET')


@pytest.mark.asyncio
async def test_stream_download(enable_api, mock_dlmgr, mock_handle, test_download, session, tmpdir):
    """
    Testing whether the API returns code 206 if we stream a non-existent download
    """
    session.dlmgr.get_download = lambda _: test_download

    with open(tmpdir / "dummy.txt", "w") as stream_file:
        stream_file.write("a" * 500)

    # Prepare a mocked stream
    stream = Mock()
    stream.seek = lambda _: succeed(None)
    stream.closed = False
    stream.filename = tmpdir / "dummy.txt"
    stream.enable = lambda *_, **__: succeed(None)
    stream.filesize = 500
    stream.piecelen = 32
    stream.seek = lambda _: succeed(None)
    stream.iterpieces = lambda *_, **__: [1]
    stream.prebuffsize = 0
    stream.lastpiece = 1
    stream.bytetopiece = lambda _: 1
    stream.pieceshave = [1, 2]
    stream.updateprios = lambda: succeed(None)
    stream.cursorpiecemap = {}
    stream.get_byte_progress = lambda _: 1
    stream.read = lambda _: succeed('a' * 500)
    test_download.stream = stream

    await do_request(session, f'downloads/{test_download.infohash}/stream/0',
                     headers={'range': 'bytes=0-'}, expected_code=206, json_response=False)


@pytest.mark.asyncio
async def test_change_hops(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 200 if we change the amount of hops of a download
    """
    session.dlmgr.get_download = lambda _: test_download
    session.dlmgr.update_hops = lambda *_: succeed(None)

    await do_request(session, 'downloads/%s' % test_download.infohash, post_data={'anon_hops': 1},
                     expected_code=200, request_type='PATCH',
                     expected_json={'modified': True, "infohash": test_download.infohash})


@pytest.mark.asyncio
async def test_change_hops_fail(enable_api, mock_dlmgr, test_download, session):
    """
    Testing whether the API returns 500 if changing the number of hops in a download fails
    """
    session.dlmgr.get_download = lambda _: test_download
    session.dlmgr.update_hops = lambda *_: fail(RuntimeError)

    await do_request(session, 'downloads/%s' % test_download.infohash, post_data={'anon_hops': 1},
                     expected_code=500, request_type='PATCH',
                     expected_json={'error': {'message': '', 'code': 'RuntimeError', 'handled': True}})


@pytest.mark.asyncio
async def test_add_metadata_download(enable_chant, enable_api, session):
    """
    Test adding a channel metadata download to the Tribler core
    """
    post_data = {'uri': 'file:%s' % (TESTS_DIR / 'data/sample_channel/channel.mdblob')}
    expected_json = {'started': True, 'infohash': 'ea95d47988b4dcb07667194c998d2c5b473132e5'}
    await do_request(session, 'downloads', expected_code=200, request_type='PUT',
                     post_data=post_data, expected_json=expected_json)
    with db_session:
        assert session.mds.ChannelMetadata.select().count() == 1
        assert session.mds.ChannelMetadata.get().subscribed


@pytest.mark.asyncio
async def test_add_metadata_download_already_added(enable_chant, enable_api, session):
    """
    Test adding a channel metadata download to the Tribler core
    """
    with db_session:
        session.mds.process_mdblob_file(TESTS_DIR / 'data/sample_channel/channel.mdblob')
    post_data = {'uri': 'file:%s' % (TESTS_DIR / 'data/sample_channel/channel.mdblob')}
    expected_json = {'error': 'Could not import Tribler metadata file'}
    await do_request(session, 'downloads', expected_code=200, request_type='PUT', post_data=post_data,
                     expected_json=expected_json)


@pytest.mark.asyncio
async def test_add_metadata_download_invalid_sig(enable_chant, enable_api, session, tmpdir):
    """
    Test whether adding metadata with an invalid signature results in an error
    """
    file_path = tmpdir / "invalid.mdblob"
    with open(file_path, "wb") as out_file:
        with db_session:
            my_channel = session.mds.ChannelMetadata.create_channel('test', 'test')

        hexed = hexlify(my_channel.serialized()).encode('utf-8')[:-5] + b"aaaaa"
        out_file.write(unhexlify(hexed))

    post_data = {'uri': f'file:{file_path}', 'metadata_download': '1'}
    expected_json = {'error': "Metadata has invalid signature"}
    await do_request(session, 'downloads', expected_code=400, request_type='PUT', post_data=post_data,
                     expected_json=expected_json)


@pytest.mark.asyncio
async def test_add_invalid_metadata_download(enable_chant, enable_api, session):
    """
    Test adding an invalid metadata download to the Tribler core
    """
    post_data = {'uri': 'file:%s' % (TESTS_DATA_DIR / 'notexisting.mdblob'), 'metadata_download': '1'}
    await do_request(session, 'downloads', expected_code=400, request_type='PUT', post_data=post_data)
