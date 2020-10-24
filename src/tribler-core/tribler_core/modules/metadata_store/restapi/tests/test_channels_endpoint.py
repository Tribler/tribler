import base64
import shutil
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.serialization import COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.restapi.base_api_test import do_request
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify


@pytest.mark.asyncio
async def test_get_channels(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query some channels in the database with the REST API
    """
    json_dict = await do_request(session, 'channels')
    assert len(json_dict['results']) == 10
    # Default channel state should be METAINFO_LOOKUP
    assert json_dict['results'][0]['state'] == CHANNEL_STATE.METAINFO_LOOKUP.value

    # We test out different combinations of channels' states and download progress
    # State UPDATING:
    session.mds.compute_channel_update_progress = lambda _: 0.5
    with db_session:
        channel = session.mds.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 123

    json_dict = await do_request(session, 'channels')
    assert json_dict['results'][0]['progress'] == 0.5

    # State DOWNLOADING
    with db_session:
        channel = session.mds.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 0

    session.dlmgr.metainfo_requests.get = lambda _: False
    session.dlmgr.download_exists = lambda _: True
    json_dict = await do_request(session, 'channels')
    assert json_dict['results'][0]['state'] == CHANNEL_STATE.DOWNLOADING.value


@pytest.mark.asyncio
async def test_get_channels_sort_by_health(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    json_dict = await do_request(session, 'channels?sort_by=health')
    assert len(json_dict['results']) == 10


@pytest.mark.asyncio
async def test_get_channels_invalid_sort(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query some channels in the database with the REST API and an invalid sort parameter
    """
    json_dict = await do_request(session, 'channels?sort_by=fdsafsdf')
    assert len(json_dict['results']) == 10


@pytest.mark.asyncio
async def test_get_subscribed_channels(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can successfully query channels we are subscribed to with the REST API
    """
    json_dict = await do_request(session, 'channels?subscribed=1')
    assert len(json_dict['results']) == 5


@pytest.mark.asyncio
async def test_get_channels_count(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test getting the total number of channels through the API
    """
    json_dict = await do_request(session, 'channels?subscribed=1&include_total=1')
    assert json_dict['total'] == 5


@pytest.mark.asyncio
async def test_create_channel(enable_chant, enable_api, session):
    """
    Test creating a channel in your channel with REST API POST request
    """
    await do_request(session, 'channels/mychannel/0/channels', request_type='POST', expected_code=200)
    with db_session:
        assert session.mds.ChannelMetadata.get(title="New channel")
    await do_request(
        session, 'channels/mychannel/0/channels', request_type='POST', post_data={"name": "foobar"}, expected_code=200
    )
    with db_session:
        assert session.mds.ChannelMetadata.get(title="foobar")


@pytest.mark.asyncio
async def test_get_contents_count(
    enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr_get_download, session
):
    """
    Test getting the total number of items in a specific channel
    """
    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
        json_dict = await do_request(session, 'channels/%s/123?include_total=1' % hexlify(chan.public_key))
    assert json_dict['total'] == 5


@pytest.mark.asyncio
async def test_get_channel_contents(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query torrents from a channel
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5
    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, 'channels/%s/123' % hexlify(chan.public_key), expected_code=200)
    print(json_dict)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


@pytest.mark.asyncio
async def test_get_channel_contents_by_type(enable_chant, enable_api, my_channel, mock_dlmgr_get_download, session):
    """
    Test filtering channel contents by a list of data types
    """
    with db_session:
        session.mds.CollectionNode(title='some_folder', origin_id=my_channel.id_)

        json_dict = await do_request(
            session,
            'channels/%s/%d?metadata_type=%d&metadata_type=%d'
            % (hexlify(my_channel.public_key), my_channel.id_, COLLECTION_NODE, REGULAR_TORRENT),
            expected_code=200,
        )

    assert len(json_dict['results']) == 10
    assert 'status' in json_dict['results'][0]


@pytest.mark.asyncio
async def test_commit_no_channel(enable_chant, enable_api, session):
    """
    Test whether we get an error if we try to commit a channel without it being created
    """
    await do_request(session, 'channels/mychannel/123/commit', expected_code=404, request_type='POST')


@pytest.mark.asyncio
async def test_commit_single_channel(enable_chant, enable_api, my_channel, mock_dlmgr, session):
    """
    Test whether we can successfully commit changes to a single personal channel with the REST API
    """
    json_dict = await do_request(session, 'channels/mychannel/%i/commit' % my_channel.id_, request_type='POST')
    assert json_dict["success"]


@pytest.mark.asyncio
async def test_commit_all_channels(enable_chant, enable_api, my_channel, mock_dlmgr, session):
    """
    Test whether we can successfully commit changes to a single personal channel with the REST API
    """
    json_dict = await do_request(session, 'channels/mychannel/0/commit', request_type='POST')
    assert json_dict["success"]


@pytest.mark.asyncio
async def test_get_commit_state(enable_chant, enable_api, my_channel, session):
    """
    Test getting dirty status of a channel through its commit endpoint
    """
    await do_request(session, 'channels/mychannel/0/commit', expected_json={'dirty': True})


@pytest.mark.asyncio
async def test_copy_torrents_to_collection(enable_chant, enable_api, session):
    """
    Test if we can copy torrents from an external channel(s) to a personal channel/collection
    """
    channel = session.mds.ChannelMetadata.create_channel('my chan')
    ext_key = default_eccrypto.generate_key(u"curve25519")
    with db_session:
        external_metadata1 = session.mds.TorrentMetadata(
            sign_with=ext_key, id_=111, title="bla1", infohash=random_infohash()
        )
        external_metadata2_ffa = session.mds.TorrentMetadata(
            public_key=b"", id_=222, title="bla2-ffa", infohash=random_infohash()
        )

    request_data = [external_metadata1.to_simple_dict(), external_metadata2_ffa.to_simple_dict()]
    await do_request(
        session,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data=request_data,
        request_type='POST',
    )
    with db_session:
        assert len(channel.contents) == 2

    await do_request(
        session,
        'collections/%s/%i/copy' % (hexlify(b"0" * 64), 777),
        post_data=request_data,
        request_type='POST',
        expected_code=404,
    )

    request_data = [{'public_key': hexlify(b"1" * 64), 'id': 12333}]
    await do_request(
        session,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data=request_data,
        request_type='POST',
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_copy_torrents_to_collection_bad_json(enable_chant, enable_api, session):
    """
    Test whether bad JSON will be rejected with an error 400 when copying torrents to a collection
    """
    channel = session.mds.ChannelMetadata.create_channel('my chan')
    await do_request(
        session,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data='abc',
        request_type='POST',
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_create_subchannel_and_collection(enable_chant, enable_api, session):
    """
    Test if we can create subchannels/collections in a personal channel
    """
    await do_request(session, 'channels/mychannel/0/channels', request_type='POST', expected_code=200)
    with db_session:
        channel = session.mds.ChannelMetadata.get()
        assert channel
    await do_request(session, 'channels/mychannel/%i/collections' % channel.id_, request_type='POST', expected_code=200)
    with db_session:
        collection = session.mds.CollectionNode.get(lambda g: g.origin_id == channel.id_)
        assert collection


@pytest.mark.asyncio
async def test_add_torrents_no_channel(enable_chant, enable_api, my_channel, session):
    """
    Test whether an error is returned when we try to add a torrent to your unexisting channel
    """
    with db_session:
        my_chan = session.mds.ChannelMetadata.get_my_channels().first()
        my_chan.delete()
        await do_request(
            session,
            'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
            request_type='PUT',
            expected_code=404,
        )


@pytest.mark.asyncio
async def test_add_torrents_no_dir(enable_chant, enable_api, my_channel, session):
    """
    Test whether an error is returned when pointing to a file instead of a directory when adding torrents
    """
    post_params = {'torrents_dir': 'nonexisting'}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_add_torrents_recursive_no_dir(enable_chant, enable_api, my_channel, session):
    """
    Test whether an error is returned when recursively adding torrents without a specified directory
    """
    post_params = {'recursive': True}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_add_torrents_from_dir(enable_chant, enable_api, my_channel, state_dir, session):
    """
    Test whether adding torrents from a directory to your channels works
    """
    post_params = {'torrents_dir': state_dir, 'recursive': True}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
    )


@pytest.mark.asyncio
async def test_add_torrent_missing_torrent(enable_chant, enable_api, my_channel, session):
    """
    Test whether an error is returned when adding a torrent to your channel but with a missing torrent parameter
    """
    post_params = {}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_add_invalid_torrent(enable_chant, enable_api, my_channel, session):
    """
    Test whether an error is returned when adding an invalid torrent file to your channel
    """
    post_params = {'torrent': 'bla'}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=500,
    )


@pytest.mark.asyncio
async def test_add_torrent_duplicate(enable_chant, enable_api, my_channel, session):
    """
    Test whether adding a duplicate torrent to you channel results in an error
    """
    with db_session:
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        my_channel.add_torrent_to_channel(tdef, {'description': 'blabla'})

        with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
            base64_content = base64.b64encode(torrent_file.read()).decode('utf-8')

            post_params = {'torrent': base64_content}
            await do_request(
                session,
                'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
                request_type='PUT',
                post_data=post_params,
                expected_code=500,
            )


@pytest.mark.asyncio
async def test_add_torrent(enable_chant, enable_api, my_channel, session):
    """
    Test adding a torrent to your channel
    """
    with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
        base64_content = base64.b64encode(torrent_file.read())

        post_params = {'torrent': base64_content.decode('utf-8')}
        await do_request(
            session,
            'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
            request_type='PUT',
            post_data=post_params,
        )


@pytest.mark.asyncio
async def test_add_torrent_invalid_uri(enable_chant, enable_api, my_channel, session):
    """
    Test whether adding a torrent to your channel with an invalid URI results in an error
    """
    post_params = {'uri': 'thisisinvalid'}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_add_torrent_from_url(enable_chant, enable_api, my_channel, tmpdir, file_server, session):
    """
    Test whether we can add a torrent to your channel from an URL
    """
    shutil.copyfile(TORRENT_UBUNTU_FILE, tmpdir / "ubuntu.torrent")
    post_params = {'uri': 'http://localhost:%d/ubuntu.torrent' % file_server}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
    )


@pytest.mark.asyncio
async def test_add_torrent_from_magnet(enable_chant, enable_api, my_channel, mock_dlmgr, session):
    """
    Test whether we can add a torrent to your channel from a magnet link
    """

    def fake_get_metainfo(_, **__):
        meta_info = TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
        return succeed(meta_info)

    session.dlmgr.get_metainfo = fake_get_metainfo
    session.mds.torrent_exists_in_personal_channel = Mock()

    post_params = {'uri': 'magnet:?xt=urn:btih:111111111111111111111111111111111111111111'}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
    )
    session.mds.torrent_exists_in_personal_channel.assert_called_once()


@pytest.mark.asyncio
async def test_add_torrent_from_magnet_error(enable_chant, enable_api, my_channel, mock_dlmgr, session):
    """
    Test whether an error while adding magnets to your channel results in a proper 500 error
    """

    def fake_get_metainfo(*_, **__):
        return succeed(None)

    session.dlmgr.get_metainfo = fake_get_metainfo

    post_params = {'uri': 'magnet:?fake'}
    await do_request(
        session,
        'channels/%s/%s/torrents' % (hexlify(my_channel.public_key), my_channel.id_),
        request_type='PUT',
        post_data=post_params,
        expected_code=500,
    )


@pytest.mark.asyncio
async def test_get_torrents(enable_chant, enable_api, my_channel, mock_dlmgr_get_download, session):
    """
    Test whether we can query some torrents in the database with the REST API
    """
    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, 'channels/%s/%d' % (hexlify(chan.public_key), my_channel.id_))
    assert len(json_dict['results']) == 9


@pytest.mark.asyncio
async def test_get_torrents_ffa_channel(enable_chant, enable_api, my_channel, mock_dlmgr_get_download, session):
    """
    Test whether we can query channel contents for unsigned (legacy/FFA) channels
    """
    with db_session:
        channel = session.mds.ChannelMetadata(title='ffa', infohash=random_infohash(), public_key=b"", id_=123)
        session.mds.TorrentMetadata(
            public_key=b"", id_=333333, origin_id=channel.id_, title='torrent', infohash=random_infohash()
        )

    def on_response(json_dict):
        assert len(json_dict['results']) == 1

    # We test for both forms of querying null-key channels
    on_response(await do_request(session, 'channels//123'))
    on_response(await do_request(session, 'channels/00/123'))
