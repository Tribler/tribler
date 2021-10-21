import base64
import json
from binascii import unhexlify
from unittest.mock import Mock, patch

from aiohttp.web_app import Application

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.gigachannel.community.gigachannel_community import NoChannelSourcesException
from tribler_core.components.metadata_store.category_filter.family_filter import default_xxx_filter
from tribler_core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler_core.components.metadata_store.restapi.channels_endpoint import ChannelsEndpoint
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.components.metadata_store.utils import RequestTimeoutException, tag_torrent
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify

PNG_DATA = unhexlify(
    "89504e470d0a1a0a0000000d494844520"
    "0000001000000010100000000376ef924"
    "0000001049444154789c626001000000f"
    "fff03000006000557bfabd40000000049454e44ae426082"
)

# pylint: disable=unused-argument


@pytest.fixture
def rest_api(loop, aiohttp_client, mock_dlmgr, metadata_store, tags_db):  # pylint: disable=unused-argument
    mock_gigachannel_manager = Mock()
    mock_gigachannel_community = Mock()

    def return_exc(*args, **kwargs):
        raise RequestTimeoutException

    mock_dlmgr.metainfo_requests = {}

    mock_gigachannel_community.remote_select_channel_contents = return_exc
    collections_endpoint = ChannelsEndpoint()
    collections_endpoint.mds = metadata_store
    collections_endpoint.tags_db = tags_db
    collections_endpoint.download_manager = mock_dlmgr
    collections_endpoint.gigachannel_manager = mock_gigachannel_manager
    collections_endpoint.gigachannel_community = mock_gigachannel_community

    channels_endpoint = ChannelsEndpoint()
    channels_endpoint.mds = metadata_store
    channels_endpoint.tags_db = tags_db
    channels_endpoint.download_manager = mock_dlmgr
    channels_endpoint.gigachannel_manager = mock_gigachannel_manager
    channels_endpoint.gigachannel_community = mock_gigachannel_community

    app = Application(middlewares=[error_middleware])
    app.add_subapp('/channels', channels_endpoint.app)
    app.add_subapp('/collections', collections_endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_channels(rest_api, add_fake_torrents_channels, mock_dlmgr, metadata_store):
    """
    Test whether we can query some channels in the database with the REST API
    """
    mock_dlmgr.download_exists = lambda *args: None
    json_dict = await do_request(rest_api, 'channels')
    assert len(json_dict['results']) == 10
    # Default channel state should be METAINFO_LOOKUP
    assert json_dict['results'][-1]['state'] == CHANNEL_STATE.METAINFO_LOOKUP.value

    # We test out different combinations of channels' states and download progress
    # State UPDATING:
    metadata_store.compute_channel_update_progress = lambda _: 0.5
    with db_session:
        channel = metadata_store.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 123

    json_dict = await do_request(rest_api, 'channels')
    assert json_dict['results'][-1]['progress'] == 0.5

    # State DOWNLOADING
    with db_session:
        channel = metadata_store.ChannelMetadata.select().first()
        channel.subscribed = True
        channel.local_version = 0

    mock_dlmgr.download_exists = lambda _: True
    json_dict = await do_request(rest_api, 'channels')
    assert json_dict['results'][-1]['state'] == CHANNEL_STATE.DOWNLOADING.value


async def test_get_channels_sort_by_health(rest_api, add_fake_torrents_channels, mock_dlmgr):
    json_dict = await do_request(rest_api, 'channels?sort_by=health')
    assert len(json_dict['results']) == 10


async def test_get_channels_invalid_sort(add_fake_torrents_channels, mock_dlmgr, rest_api):
    """
    Test whether we can query some channels in the database with the REST API and an invalid sort parameter
    """
    json_dict = await do_request(rest_api, 'channels?sort_by=fdsafsdf')
    assert len(json_dict['results']) == 10


async def test_get_subscribed_channels(add_fake_torrents_channels, mock_dlmgr, rest_api):
    """
    Test whether we can successfully query channels we are subscribed to with the REST API
    """
    json_dict = await do_request(rest_api, 'channels?subscribed=1')
    assert len(json_dict['results']) == 5


async def test_get_channels_count(add_fake_torrents_channels, mock_dlmgr, rest_api):
    """
    Test getting the total number of channels through the API
    """
    json_dict = await do_request(rest_api, 'channels?subscribed=1&include_total=1')
    assert json_dict['total'] == 5


async def test_create_channel(rest_api, metadata_store):
    """
    Test creating a channel in your channel with REST API POST request
    """
    await do_request(rest_api, 'channels/mychannel/0/channels', request_type='POST', expected_code=200)
    with db_session:
        assert metadata_store.ChannelMetadata.get(title="New channel")
    await do_request(
        rest_api, 'channels/mychannel/0/channels', request_type='POST', post_data={"name": "foobar"}, expected_code=200
    )
    with db_session:
        assert metadata_store.ChannelMetadata.get(title="foobar")


async def test_get_contents_count(add_fake_torrents_channels, mock_dlmgr, rest_api, metadata_store):
    """
    Test getting the total number of items in a specific channel
    """
    mock_dlmgr.get_download = lambda _: None
    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
        json_dict = await do_request(rest_api, f'channels/{hexlify(chan.public_key)}/123?include_total=1')
    assert json_dict['total'] == 5


async def test_get_channel_contents(metadata_store, add_fake_torrents_channels, mock_dlmgr, rest_api):
    """
    Test whether we can query torrents from a channel
    """
    mock_dlmgr.get_download().get_state().get_progress = lambda: 0.5
    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
    json_dict = await do_request(rest_api, f'channels/{hexlify(chan.public_key)}/123', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


async def test_get_channel_contents_remote(metadata_store, add_fake_torrents_channels, mock_dlmgr, rest_api):
    """
    Test whether we can query torrents from a channel from a remote peer
    """
    mock_dlmgr.get_download().get_state().get_progress = lambda: 0.5

    async def mock_select(**kwargs):
        with db_session:
            return [r.to_simple_dict() for r in metadata_store.get_entries(**kwargs)]

    rest_api.gigachannel_community = Mock()
    rest_api.gigachannel_community.remote_select_channel_contents = mock_select
    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
    json_dict = await do_request(rest_api, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


async def test_get_channel_contents_remote_request_timeout(
    metadata_store, add_fake_torrents_channels, mock_dlmgr, rest_api
):
    """
    Test whether we can query torrents from a channel from a remote peer.
    In case of remote query timeout, the results should still be served from the local DB
    """
    mock_dlmgr.get_download().get_state().get_progress = lambda: 0.5

    async def mock_select(**kwargs):
        raise RequestTimeoutException()

    rest_api.gigachannel_community = Mock()
    rest_api.gigachannel_community.remote_select_channel_contents = mock_select

    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
    json_dict = await do_request(rest_api, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]
    assert json_dict['results'][0]['progress'] == 0.5


async def test_get_channel_contents_remote_request_no_peers(
    add_fake_torrents_channels, mock_dlmgr_get_download, rest_api, metadata_store
):
    """
    Test whether we can query torrents from a channel from a remote peer.
    In case of zero available remote sources for the channel, the results should still be served from the local DB
    """

    async def mock_select(**kwargs):
        raise NoChannelSourcesException()

    rest_api.gigachannel_community = Mock()
    rest_api.gigachannel_community.remote_select_channel_contents = mock_select

    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
    json_dict = await do_request(rest_api, f'channels/{hexlify(chan.public_key)}/123?remote=1', expected_code=200)
    assert len(json_dict['results']) == 5
    assert 'status' in json_dict['results'][0]


async def test_get_channel_description(rest_api, metadata_store):
    """
    Test getting description of the channel from the database
    """
    descr_txt = "foobar"
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
        channel_description = metadata_store.ChannelDescription(
            origin_id=chan.id_, json_text=json.dumps({"description_text": descr_txt})
        )
    response_dict = await do_request(
        rest_api, f'channels/{hexlify(chan.public_key)}/{chan.id_}/description', expected_code=200
    )
    assert response_dict == json.loads(channel_description.json_text)


async def test_put_new_channel_description(rest_api, metadata_store):
    """
    Test adding description to a channel
    """
    new_descr = "lalala"
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
    response_dict = await do_request(
        rest_api,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/description',
        request_type="PUT",
        post_data={"description_text": new_descr},
        expected_code=200,
    )

    assert response_dict == {"description_text": new_descr}

    # Test updating description of a channel
    updated_descr = "foobar"
    response_dict = await do_request(
        rest_api,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/description',
        request_type="PUT",
        post_data={"description_text": updated_descr},
        expected_code=200,
    )

    assert response_dict == {"description_text": updated_descr}


async def test_get_popular_torrents(add_fake_torrents_channels, mock_dlmgr_get_download, mock_dlmgr, rest_api):
    """
    Test getting the list of popular torrents. The list is served as contents of a pseudo-channel
    """
    json_dict = await do_request(rest_api, 'channels/popular_torrents', expected_code=200)

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


async def test_get_popular_torrents_mdtype(add_fake_torrents_channels, mock_dlmgr_get_download, rest_api):
    """
    It should be not possible to specify metadata_type argument for popular torrents endpoint
    """
    json_dict1 = await do_request(rest_api, 'channels/popular_torrents')
    json_dict2 = await do_request(rest_api, 'channels/popular_torrents?metadata_type=300')
    json_dict3 = await do_request(rest_api, 'channels/popular_torrents?metadata_type=400')

    # Currently popularity page force-set metadata_type to 300 (REGULAR_TORRENT) for all requests
    assert json_dict1 == json_dict2 == json_dict3


async def test_get_channel_contents_by_type(metadata_store, my_channel, mock_dlmgr_get_download, rest_api):
    """
    Test filtering channel contents by a list of data types
    """
    with db_session:
        metadata_store.CollectionNode(title='some_folder', origin_id=my_channel.id_)

        json_dict = await do_request(
            rest_api,
            'channels/%s/%d?metadata_type=%d&metadata_type=%d'
            % (hexlify(my_channel.public_key), my_channel.id_, COLLECTION_NODE, REGULAR_TORRENT),
            expected_code=200,
        )

    assert len(json_dict['results']) == 10
    assert 'status' in json_dict['results'][0]


async def test_commit_no_channel(rest_api):
    """
    Test whether we get an error if we try to commit a channel without it being created
    """
    await do_request(rest_api, 'channels/mychannel/123/commit', expected_code=404, request_type='POST')


async def test_commit_single_channel(my_channel, mock_dlmgr, rest_api):
    """
    Test whether we can successfully commit changes to a single personal channel with the REST API
    """
    json_dict = await do_request(rest_api, 'channels/mychannel/%i/commit' % my_channel.id_, request_type='POST')
    assert json_dict["success"]


async def test_commit_all_channels(my_channel, mock_dlmgr, rest_api):
    """
    Test whether we can successfully commit changes to a single personal channel with the REST API
    """
    json_dict = await do_request(rest_api, 'channels/mychannel/0/commit', request_type='POST')
    assert json_dict["success"]


async def test_get_commit_state(my_channel, rest_api):
    """
    Test getting dirty status of a channel through its commit endpoint
    """
    await do_request(rest_api, 'channels/mychannel/0/commit', expected_json={'dirty': True})


async def test_copy_torrents_to_collection(rest_api, metadata_store):
    """
    Test if we can copy torrents from an external channel(s) to a personal channel/collection
    """
    channel = metadata_store.ChannelMetadata.create_channel('my chan')
    ext_key = default_eccrypto.generate_key("curve25519")
    with db_session:
        external_metadata1 = metadata_store.TorrentMetadata(
            sign_with=ext_key, id_=111, title="bla1", infohash=random_infohash()
        )
        external_metadata2_ffa = metadata_store.TorrentMetadata(
            public_key=b"", id_=222, title="bla2-ffa", infohash=random_infohash()
        )

    request_data = [external_metadata1.to_simple_dict(), external_metadata2_ffa.to_simple_dict()]
    await do_request(
        rest_api,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data=request_data,
        request_type='POST',
    )
    with db_session:
        assert len(channel.contents) == 2

    await do_request(
        rest_api,
        'collections/%s/%i/copy' % (hexlify(b"0" * 64), 777),
        post_data=request_data,
        request_type='POST',
        expected_code=404,
    )

    request_data = [{'public_key': hexlify(b"1" * 64), 'id': 12333}]
    await do_request(
        rest_api,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data=request_data,
        request_type='POST',
        expected_code=400,
    )


async def test_copy_torrents_to_collection_bad_json(metadata_store, rest_api):
    """
    Test whether bad JSON will be rejected with an error 400 when copying torrents to a collection
    """
    channel = metadata_store.ChannelMetadata.create_channel('my chan')
    await do_request(
        rest_api,
        'collections/%s/%i/copy' % (hexlify(channel.public_key), channel.id_),
        post_data='abc',
        request_type='POST',
        expected_code=400,
    )


async def test_create_subchannel_and_collection(metadata_store, rest_api):
    """
    Test if we can create subchannels/collections in a personal channel
    """
    await do_request(rest_api, 'channels/mychannel/0/channels', request_type='POST', expected_code=200)
    with db_session:
        channel = metadata_store.ChannelMetadata.get()
        assert channel
    await do_request(
        rest_api, 'channels/mychannel/%i/collections' % channel.id_, request_type='POST', expected_code=200
    )
    with db_session:
        collection = metadata_store.CollectionNode.get(lambda g: g.origin_id == channel.id_)
        assert collection


async def test_add_torrents_no_channel(metadata_store, my_channel, rest_api):
    """
    Test whether an error is returned when we try to add a torrent to your unexisting channel
    """
    with db_session:
        my_chan = metadata_store.ChannelMetadata.get_my_channels().first()
        my_chan.delete()
        await do_request(
            rest_api,
            f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
            request_type='PUT',
            expected_code=404,
        )


async def test_add_torrents_no_dir(my_channel, rest_api):
    """
    Test whether an error is returned when pointing to a file instead of a directory when adding torrents
    """
    post_params = {'torrents_dir': 'nonexisting'}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


async def test_add_torrents_recursive_no_dir(my_channel, rest_api):
    """
    Test whether an error is returned when recursively adding torrents without a specified directory
    """
    post_params = {'recursive': True}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


async def test_add_torrents_from_dir(my_channel, state_dir, rest_api):
    """
    Test whether adding torrents from a directory to your channels works
    """
    post_params = {'torrents_dir': str(state_dir), 'recursive': True}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
    )


async def test_add_torrent_missing_torrent(my_channel, rest_api):
    """
    Test whether an error is returned when adding a torrent to your channel but with a missing torrent parameter
    """
    post_params = {}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


async def test_add_invalid_torrent(my_channel, rest_api):
    """
    Test whether an error is returned when adding an invalid torrent file to your channel
    """
    post_params = {'torrent': 'bla'}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=500,
    )


async def test_add_torrent_duplicate(my_channel, rest_api):
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
                rest_api,
                f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
                request_type='PUT',
                post_data=post_params,
                expected_code=200,
            )


async def test_add_torrent(my_channel, rest_api):
    """
    Test adding a torrent to your channel
    """
    with open(TORRENT_UBUNTU_FILE, "rb") as torrent_file:
        base64_content = base64.b64encode(torrent_file.read())

        post_params = {'torrent': base64_content.decode('utf-8')}
        await do_request(
            rest_api,
            f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
            request_type='PUT',
            post_data=post_params,
        )


async def test_add_torrent_invalid_uri(my_channel, rest_api):
    """
    Test whether adding a torrent to your channel with an invalid URI results in an error
    """
    post_params = {'uri': 'thisisinvalid'}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=400,
    )


async def test_add_torrent_from_url(my_channel, tmpdir, rest_api):
    """
    Test whether we can add a torrent to your channel from an URL
    """
    post_params = {'uri': 'http://localhost:123/ubuntu.torrent'}

    async def _mock_fetch(*args):
        with open(TORRENT_UBUNTU_FILE, 'rb') as f:
            return f.read()

    with patch('tribler_core.components.metadata_store.restapi.channels_endpoint._fetch_uri', new=_mock_fetch):
        await do_request(
            rest_api,
            f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
            request_type='PUT',
            post_data=post_params,
        )


async def test_add_torrent_from_magnet(my_channel, mock_dlmgr, rest_api, metadata_store):
    """
    Test whether we can add a torrent to your channel from a magnet link
    """

    def fake_get_metainfo(_, **__):
        meta_info = TorrentDef.load(TORRENT_UBUNTU_FILE).get_metainfo()
        return succeed(meta_info)

    mock_dlmgr.get_metainfo = fake_get_metainfo
    metadata_store.torrent_exists_in_personal_channel = Mock()

    post_params = {'uri': 'magnet:?xt=urn:btih:111111111111111111111111111111111111111111'}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
    )
    metadata_store.torrent_exists_in_personal_channel.assert_called_once()


async def test_add_torrent_from_magnet_error(my_channel, mock_dlmgr, rest_api):
    """
    Test whether an error while adding magnets to your channel results in a proper 500 error
    """

    def fake_get_metainfo(*_, **__):
        return succeed(None)

    mock_dlmgr.get_metainfo = fake_get_metainfo

    post_params = {'uri': 'magnet:?fake'}
    await do_request(
        rest_api,
        f'channels/{hexlify(my_channel.public_key)}/{my_channel.id_}/torrents',
        request_type='PUT',
        post_data=post_params,
        expected_code=500,
    )


async def test_get_torrents(my_channel, mock_dlmgr_get_download, rest_api, metadata_store):
    """
    Test whether we can query some torrents in the database with the REST API
    """
    with db_session:
        chan = metadata_store.ChannelMetadata.select().first()
    json_dict = await do_request(rest_api, 'channels/%s/%d' % (hexlify(chan.public_key), my_channel.id_))
    assert len(json_dict['results']) == 9


async def test_get_torrents_ffa_channel(my_channel, mock_dlmgr_get_download, rest_api, metadata_store):
    """
    Test whether we can query channel contents for unsigned (legacy/FFA) channels
    """
    with db_session:
        channel = metadata_store.ChannelMetadata(title='ffa', infohash=random_infohash(), public_key=b"", id_=123)
        metadata_store.TorrentMetadata(
            public_key=b"", id_=333333, origin_id=channel.id_, title='torrent', infohash=random_infohash()
        )

    def on_response(json_dict):
        assert len(json_dict['results']) == 1

    on_response(await do_request(rest_api, 'channels/00/123'))


async def test_put_channel_thumbnail(rest_api, metadata_store):
    """
    Test adding description to a channel
    """
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
    await do_request(
        rest_api,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail',
        request_type="PUT",
        headers={'Content-Type': 'image/png'},
        json_response=False,
        post_data=PNG_DATA,
        expected_code=201,
    )
    with db_session:
        obj = metadata_store.ChannelThumbnail.get(public_key=chan.public_key, origin_id=chan.id_)
    assert obj.binary_data == PNG_DATA
    assert obj.data_type == 'image/png'

    # Test updating channel thumbnail
    await do_request(
        rest_api,
        f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail',
        request_type="PUT",
        headers={'Content-Type': 'image/foo'},
        json_response=False,
        post_data=b"ffff",
        expected_code=201,
    )
    with db_session:
        obj = metadata_store.ChannelThumbnail.get(public_key=chan.public_key, origin_id=chan.id_)
    assert obj.binary_data == b"ffff"
    assert obj.data_type == 'image/foo'


async def test_get_channel_thumbnail(rest_api, metadata_store):
    """
    Test getting a channel thumbnail from MetadataStore
    """

    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
        metadata_store.ChannelThumbnail(
            public_key=chan.public_key, origin_id=chan.id_, binary_data=PNG_DATA, data_type="image/png"
        )
        endpoint = f'channels/{hexlify(chan.public_key)}/{chan.id_}/thumbnail'
        url = f'/{endpoint}'
        async with rest_api.request("GET", url, ssl=False) as response:
            assert response.status == 200
            assert await response.read() == PNG_DATA
            assert response.headers["Content-Type"] == "image/png"


async def test_get_my_channel_tags(metadata_store, mock_dlmgr_get_download, my_channel, rest_api):  # pylint: disable=redefined-outer-name
    """
    Test whether tags are correctly returned over the REST API
    """
    with db_session:
        json_dict = await do_request(
            rest_api,
            'channels/%s/%d?metadata_type=%d'
            % (hexlify(my_channel.public_key), my_channel.id_, REGULAR_TORRENT),
            expected_code=200,
        )

    assert len(json_dict['results']) == 9
    for item in json_dict['results']:
        assert len(item["tags"]) >= 2


async def test_get_my_channel_tags_xxx(metadata_store, tags_db, mock_dlmgr_get_download, my_channel, rest_api):  # pylint: disable=redefined-outer-name
    """
    Test whether XXX tags are correctly filtered
    """
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel('test', 'test')
        infohash = random_infohash()
        _ = metadata_store.TorrentMetadata(origin_id=chan.id_, title='taggedtorrent', status=NEW, infohash=infohash)
        default_xxx_filter.xxx_terms = {"wrongterm"}

        # Add a few tags to our new torrent
        tags = ["totally safe", "wrongterm", "wRonGtErM", "a wrongterm b"]
        tag_torrent(infohash, tags_db, tags=tags)

        json_dict = await do_request(
            rest_api,
            'channels/%s/%d?metadata_type=%d&hide_xxx=1'
            % (hexlify(my_channel.public_key), chan.id_, REGULAR_TORRENT),
            expected_code=200,
        )

    assert len(json_dict['results']) == 1
    assert len(json_dict['results'][0]["tags"]) == 1
