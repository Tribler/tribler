import base64
import shutil
from binascii import unhexlify
from unittest.mock import Mock

from aiohttp import ClientSession

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.community.gigachannel_community import NoChannelSourcesException
from tribler_core.modules.metadata_store.community.remote_query_community import RequestTimeoutException
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.restapi.base_api_test import do_request
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.json_util import dumps, loads
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify

PNG_DATA = unhexlify(
    "89504e470d0a1a0a0000000d494844520"
    "0000001000000010100000000376ef924"
    "0000001049444154789c626001000000f"
    "fff03000006000557bfabd40000000049454e44ae426082"
)

# pylint: disable=unused-argument


@pytest.mark.asyncio
async def test_get_channels(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query some channels in the database with the REST API
    """
    json_dict = await do_request(session, 'channels')
    assert len(json_dict['results']) == 10
    # Default channel state should be METAINFO_LOOKUP
    assert json_dict['results'][-1]['state'] == CHANNEL_STATE.METAINFO_LOOKUP.value

    # We test out different combinations of channels' states and download progress
    # State UPDATING:
    session.mds.compute_channel_update_progress = lambda _: 0.5
    with db_session:
        channel = session.mds.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 123

    json_dict = await do_request(session, 'channels')
    assert json_dict['results'][-1]['progress'] == 0.5

    # State DOWNLOADING
    with db_session:
        channel = session.mds.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 0

    session.dlmgr.metainfo_requests.get = lambda _: False
    session.dlmgr.download_exists = lambda _: True
    json_dict = await do_request(session, 'channels')
    assert json_dict['results'][-1]['state'] == CHANNEL_STATE.DOWNLOADING.value


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
        json_dict = await do_request(session, f'channels/{hexlify(chan.public_key)}/123?include_total=1')
    assert json_dict['total'] == 5


@pytest.mark.asyncio
async def test_get_channel_contents(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query torrents from a channel
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5
    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, f'channels/{hexlify(chan.public_key)}/123', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


@pytest.mark.asyncio
async def test_get_channel_contents_remote(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test whether we can query torrents from a channel from a remote peer
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5

    async def mock_select(**kwargs):
        with db_session:
            return [r.to_simple_dict() for r in session.mds.get_entries(**kwargs)]

    session.gigachannel_community = Mock()
    session.gigachannel_community.remote_select_channel_contents = mock_select
    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


@pytest.mark.asyncio
async def test_get_channel_contents_remote_request_timeout(
    enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session
):
    """
    Test whether we can query torrents from a channel from a remote peer.
    In case of remote query timeout, the results should still be served from the local DB
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5

    async def mock_select(**kwargs):
        raise RequestTimeoutException()

    session.gigachannel_community = Mock()
    session.gigachannel_community.remote_select_channel_contents = mock_select

    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


@pytest.mark.asyncio
async def test_get_channel_contents_remote_request_no_peers(
    enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session
):
    """
    Test whether we can query torrents from a channel from a remote peer.
    In case of zero available remote sources for the channel, the results should still be served from the local DB
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5

    async def mock_select(**kwargs):
        raise NoChannelSourcesException()

    session.gigachannel_community = Mock()
    session.gigachannel_community.remote_select_channel_contents = mock_select

    with db_session:
        chan = session.mds.ChannelMetadata.select().first()
    json_dict = await do_request(session, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


@pytest.mark.asyncio
async def test_get_channel_description(enable_chant, enable_api, session):
    """
    Test getting description of the channel from the database
    """
    descr_txt = "foobar"
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
        channel_description = session.mds.ChannelDescription(
            origin_id=chan.id_, json_text=dumps({"description_text": descr_txt})
        )
    response_dict = await do_request(
        session, f'channels/{hexlify(chan.public_key)}/{chan.id_}/description', expected_code=200
    )
    assert response_dict == loads(channel_description.json_text)


@pytest.mark.asyncio
async def test_put_new_channel_description(enable_chant, enable_api, session):
    """
    Test adding description to a channel
    """
    new_descr = "lalala"
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
    response_dict = await do_request(
        session,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/description',
        request_type="PUT",
        post_data={"description_text": new_descr},
        expected_code=200,
    )

    assert response_dict == {"description_text": new_descr}

    # Test updating description of a channel
    updated_descr = "foobar"
    response_dict = await do_request(
        session,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/description',
        request_type="PUT",
        post_data={"description_text": updated_descr},
        expected_code=200,
    )

    assert response_dict == {"description_text": updated_descr}


@pytest.mark.asyncio
async def test_get_popular_torrents(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    Test getting the list of popular torrents. The list is served as contents of a pseudo-channel
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5
    json_dict = await do_request(session, 'channels/popular_torrents', expected_code=200)

    def fields(d, *args):
        return {key: d[key] for key in args}

    seeders_orig_order = [fields(d, 'type', 'num_seeders', 'num_leechers') for d in json_dict['results']]

    def sort_key(d):
        a = 1 if d["type"] == CHANNEL_TORRENT else 2 if d["type"] == COLLECTION_NODE else 3
        b = -d["num_seeders"]
        c = -d["num_leechers"]
        return (a, b, c)

    assert seeders_orig_order == sorted(seeders_orig_order, key=sort_key)
    assert len(json_dict['results']) == 30  # torrents 1, 3, 5 in each of 10 channels


@pytest.mark.asyncio
async def test_get_popular_torrents_mdtype(enable_chant, enable_api, add_fake_torrents_channels, mock_dlmgr, session):
    """
    It should be not possible to specify metadata_type argument for popular torrents endpoint
    """
    session.dlmgr.get_download().get_state().get_progress = lambda: 0.5
    json_dict1 = await do_request(session, 'channels/popular_torrents')
    json_dict2 = await do_request(session, 'channels/popular_torrents?metadata_type=300')
    json_dict3 = await do_request(session, 'channels/popular_torrents?metadata_type=400')

    # Currently popularity page force-set metadata_type to 300 (REGULAR_TORRENT) for all requests
    assert json_dict1 == json_dict2 == json_dict3


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
    ext_key = default_eccrypto.generate_key("curve25519")
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
            f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=500,
    )


@pytest.mark.asyncio
async def test_add_torrent_duplicate(enable_chant, enable_api, my_channel, session):
    """
    Test that adding a duplicate torrent to you channel does not result in an error
    """
    with db_session:
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        my_channel.add_torrent_to_channel(tdef, {'description': 'blabla'})

        with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
            base64_content = base64.b64encode(torrent_file.read()).decode('utf-8')

            post_params = {'torrent': base64_content}
            await do_request(
                session,
                f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
                request_type='PUT',
                post_data=post_params,
                expected_code=200,
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
            f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
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


@pytest.mark.asyncio
async def test_put_channel_thumbnail(enable_chant, enable_api, session):
    """
    Test adding description to a channel
    """
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
    await do_request(
        session,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail',
        request_type="PUT",
        headers={'Content-Type': 'image/png'},
        json_response=False,
        post_data=PNG_DATA,
        expected_code=201,
    )
    with db_session:
        obj = session.mds.ChannelThumbnail.get(public_key=chan.public_key, origin_id=chan.id_)
    assert obj.binary_data == PNG_DATA
    assert obj.data_type == 'image/png'

    # Test updating channel thumbnail
    await do_request(
        session,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail',
        request_type="PUT",
        headers={'Content-Type': 'image/foo'},
        json_response=False,
        post_data=b"ffff",
        expected_code=201,
    )
    with db_session:
        obj = session.mds.ChannelThumbnail.get(public_key=chan.public_key, origin_id=chan.id_)
    assert obj.binary_data == b"ffff"
    assert obj.data_type == 'image/foo'


@pytest.mark.asyncio
async def test_get_channel_thumbnail(enable_chant, enable_api, session):
    """
    Test getting a channel thumbnail from MetadataStore
    """

    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
        session.mds.ChannelThumbnail(
            public_key=chan.public_key, origin_id=chan.id_, binary_data=PNG_DATA, data_type="image/png"
        )
    async with ClientSession() as cl_session:
        endpoint = f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail'
        url = f'http://localhost:{session.config.get_api_http_port()}/{endpoint}'
        async with cl_session.request("GET", url, ssl=False) as response:
            assert response.status == 200
            assert await response.read() == PNG_DATA
            assert response.headers["Content-Type"] == "image/png"
