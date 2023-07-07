import json
from unittest.mock import MagicMock

import pytest
from pony.orm import db_session

from tribler.core.components.metadata_store.db.orm_bindings.channel_node import COMMITTED, TODELETE, UPDATED
from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpoint, TORRENT_CHECK_TIMEOUT
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash


# pylint: disable=unused-argument, redefined-outer-name

@pytest.fixture
async def torrent_checker(mock_dlmgr, metadata_store):
    # Initialize the torrent checker
    config = TriblerConfig()
    config.download_defaults.number_hops = 0
    tracker_manager = MagicMock()
    tracker_manager.blacklist = []
    notifier = MagicMock()
    torrent_checker = TorrentChecker(
        config=config,
        download_manager=mock_dlmgr,
        tracker_manager=tracker_manager,
        metadata_store=metadata_store,
        notifier=notifier,
        socks_listen_ports=[2000, 3000],
    )
    await torrent_checker.initialize()
    yield torrent_checker
    await torrent_checker.shutdown()


@pytest.fixture
def endpoint(torrent_checker, metadata_store):
    return MetadataEndpoint(torrent_checker, metadata_store)


async def test_update_multiple_metadata_entries(metadata_store, add_fake_torrents_channels, rest_api):
    """
    Test updating attributes of several metadata entities at once with a PATCH request to REST API
    """
    # Test handling the wrong/empty JSON gracefully
    await do_request(rest_api, 'metadata', expected_code=400, request_type='PATCH', post_data='abc')

    # Test trying update a non-existing entry
    await do_request(
        rest_api,
        'metadata',
        post_data=[{'public_key': hexlify(b'1' * 64), 'id': 111}],
        expected_code=404,
        request_type='PATCH',
    )
    with db_session:
        md1 = metadata_store.TorrentMetadata(title='old1', infohash=random_infohash())
        md2 = metadata_store.ChannelMetadata(title='old2', infohash=random_infohash(), subscribed=False)

    NEW_NAME1 = "updated1"
    NEW_NAME2 = "updated2"
    patch_data = [
        {'public_key': hexlify(md1.public_key), 'id': md1.id_, 'title': NEW_NAME1},
        {'public_key': hexlify(md2.public_key), 'id': md2.id_, 'title': NEW_NAME2, 'subscribed': 1},
    ]
    await do_request(rest_api, 'metadata', post_data=patch_data, expected_code=200, request_type='PATCH')
    with db_session:
        entry1 = metadata_store.ChannelNode.get(rowid=md1.rowid)
        assert NEW_NAME1 == entry1.title
        assert UPDATED == entry1.status

        entry2 = metadata_store.ChannelNode.get(rowid=md2.rowid)
        assert NEW_NAME2 == entry2.title
        assert UPDATED == entry2.status
        assert entry2.subscribed


async def test_delete_multiple_metadata_entries(rest_api, metadata_store):
    """
    Test deleting multiple entries with JSON REST API
    """
    with db_session:
        md1 = metadata_store.TorrentMetadata(title='old1', infohash=random_infohash())
        md2 = metadata_store.TorrentMetadata(title='old2', infohash=random_infohash())
        assert metadata_store.ChannelNode.select().count() == 2

    patch_data = [
        {'public_key': hexlify(md1.public_key), 'id': md1.id_},
        {'public_key': hexlify(md2.public_key), 'id': md2.id_},
    ]
    await do_request(rest_api, 'metadata', post_data=patch_data, expected_code=200, request_type='DELETE')
    with db_session:
        assert metadata_store.ChannelNode.select().count() == 0


async def test_update_entry_missing_json(metadata_store, rest_api):
    """
    Test whether an error is returned if we try to change entry with the REST API and missing JSON data
    """
    channel_pk = hexlify(metadata_store.ChannelNode._my_key.pub().key_to_bin()[10:])
    await do_request(rest_api, f'metadata/{channel_pk}/123', expected_code=400, request_type='PATCH', post_data='abc')


async def test_update_entry_not_found(metadata_store, rest_api):
    """
    Test whether an error is returned if we try to change some metadata entry that is not there
    """
    patch_params = {'subscribed': '1'}
    await do_request(rest_api, 'metadata/aa/123', expected_code=404, request_type='PATCH', post_data=patch_params)


async def test_update_entry_status_and_name(metadata_store, rest_api):
    """
    Test whether an error is returned if try to modify both the status and name of a torrent
    """
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
    patch_params = {'status': TODELETE, 'title': 'test'}
    await do_request(
        rest_api,
        'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
        request_type='PATCH',
        post_data=patch_params,
        expected_code=400,
    )


async def test_update_entry(rest_api, metadata_store):
    """
    Test updating a metadata entry with REST API
    """
    new_title = 'bla2'
    new_tags = "Compressed"

    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel(title="bla")
        chan.status = COMMITTED

    patch_params = {'title': new_title, 'tags': new_tags}

    result = await do_request(
        rest_api,
        'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
        request_type='PATCH',
        post_data=patch_params,
        expected_code=200,
    )

    assert new_title == result['name']
    assert new_tags == result['category']
    with db_session:
        chan = metadata_store.ChannelMetadata.get_my_channels().first()
        assert chan.status == UPDATED
        assert chan.tags == new_tags
        assert chan.title == new_title


async def test_get_entry(rest_api, metadata_store):
    """
    Test getting an entry with REST API GET request
    """
    for md_type, kwargs in (
            (
                    metadata_store.TorrentMetadata,
                    {"title": "bla", "infohash": random_infohash(),
                     "tracker_info": "http://sometracker.local/announce"},
            ),
            (
                    metadata_store.ChannelDescription,
                    {
                        "text": json.dumps(
                            {"description_text": "*{{}bla <\\> [)]// /ee2323㋛㋛㋛  ", "channel_thumbnail": "ffffff.jpg"}
                        )
                    },
            ),
    ):
        with db_session:
            md = md_type(**kwargs)
            md.status = COMMITTED
        await do_request(
            rest_api,
            'metadata/%s/%i' % (hexlify(md.public_key), md.id_),
            expected_json=md.to_simple_dict(),
        )


async def test_get_entry_not_found(rest_api, metadata_store):
    """
    Test trying to get a non-existing entry with the REST API GET request
    """
    await do_request(rest_api, 'metadata/%s/%i' % (hexlify(b"0" * 64), 123), expected_code=404)


async def test_check_torrent_health(rest_api, mock_dlmgr, udp_tracker, metadata_store):
    """
    Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
    """
    infohash = b'a' * 20
    url = f'metadata/torrents/{hexlify(infohash)}/health?timeout={TORRENT_CHECK_TIMEOUT}'
    json_response = await do_request(rest_api, url)
    assert json_response == {'checking': True}


async def test_check_torrent_query(rest_api, udp_tracker, metadata_store):
    """
    Test that the endpoint responds with an error message if the timeout parameter has a wrong value
    """
    infohash = b'a' * 20
    await do_request(rest_api, f"metadata/torrents/{infohash}/health?timeout=wrong_value&refresh=1", expected_code=400)
