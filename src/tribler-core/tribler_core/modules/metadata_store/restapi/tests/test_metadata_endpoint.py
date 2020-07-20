from ipv8.util import succeed

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.orm_bindings.channel_node import COMMITTED, TODELETE, UPDATED
from tribler_core.modules.metadata_store.restapi.metadata_endpoint import TORRENT_CHECK_TIMEOUT
from tribler_core.modules.torrent_checker.torrent_checker import TorrentChecker
from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import has_bep33_support


@pytest.mark.asyncio
async def test_update_multiple_metadata_entries(enable_chant, enable_api, add_fake_torrents_channels, session):
    """
    Test updating attributes of several metadata entities at once with a PATCH request to REST API
    """
    # Test handling the wrong/empty JSON gracefully
    await do_request(session, 'metadata', expected_code=400, request_type='PATCH', post_data='abc')

    # Test trying update a non-existing entry
    await do_request(
        session,
        'metadata',
        post_data=[{'public_key': hexlify(b'1' * 64), 'id': 111}],
        expected_code=404,
        request_type='PATCH',
    )
    with db_session:
        md1 = session.mds.TorrentMetadata(title='old1', infohash=random_infohash())
        md2 = session.mds.ChannelMetadata(title='old2', infohash=random_infohash(), subscribed=False)

    NEW_NAME1 = "updated1"
    NEW_NAME2 = "updated2"
    patch_data = [
        {'public_key': hexlify(md1.public_key), 'id': md1.id_, 'title': NEW_NAME1},
        {'public_key': hexlify(md2.public_key), 'id': md2.id_, 'title': NEW_NAME2, 'subscribed': 1},
    ]
    await do_request(session, 'metadata', post_data=patch_data, expected_code=200, request_type='PATCH')
    with db_session:
        entry1 = session.mds.ChannelNode.get(rowid=md1.rowid)
        assert NEW_NAME1 == entry1.title
        assert UPDATED == entry1.status

        entry2 = session.mds.ChannelNode.get(rowid=md2.rowid)
        assert NEW_NAME2 == entry2.title
        assert UPDATED == entry2.status
        assert entry2.subscribed


@pytest.mark.asyncio
async def test_delete_multiple_metadata_entries(enable_chant, enable_api, session):
    """
    Test deleting multiple entries with JSON REST API
    """
    with db_session:
        md1 = session.mds.TorrentMetadata(title='old1', infohash=random_infohash())
        md2 = session.mds.TorrentMetadata(title='old2', infohash=random_infohash())
        assert session.mds.ChannelNode.select().count() == 2

    patch_data = [
        {'public_key': hexlify(md1.public_key), 'id': md1.id_},
        {'public_key': hexlify(md2.public_key), 'id': md2.id_},
    ]
    await do_request(session, 'metadata', post_data=patch_data, expected_code=200, request_type='DELETE')
    with db_session:
        assert session.mds.ChannelNode.select().count() == 0


@pytest.mark.asyncio
async def test_update_entry_missing_json(enable_chant, enable_api, session):
    """
    Test whether an error is returned if we try to change entry with the REST API and missing JSON data
    """
    channel_pk = hexlify(session.mds.ChannelNode._my_key.pub().key_to_bin()[10:])
    await do_request(session, 'metadata/%s/123' % channel_pk, expected_code=400, request_type='PATCH', post_data='abc')


@pytest.mark.asyncio
async def test_update_entry_not_found(enable_chant, enable_api, session):
    """
    Test whether an error is returned if we try to change some metadata entry that is not there
    """
    patch_params = {'subscribed': '1'}
    await do_request(session, 'metadata/aa/123', expected_code=404, request_type='PATCH', post_data=patch_params)


@pytest.mark.asyncio
async def test_update_entry_status_and_name(enable_chant, enable_api, session):
    """
    Test whether an error is returned if try to modify both the status and name of a torrent
    """
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
    patch_params = {'status': TODELETE, 'title': 'test'}
    await do_request(
        session,
        'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
        request_type='PATCH',
        post_data=patch_params,
        expected_code=400,
    )


@pytest.mark.asyncio
async def test_update_entry(enable_chant, enable_api, session):
    """
    Test updating a metadata entry with REST API
    """
    new_title = 'bla2'
    new_tags = "Compressed"

    with db_session:
        chan = session.mds.ChannelMetadata.create_channel(title="bla")
        chan.status = COMMITTED

    patch_params = {'title': new_title, 'tags': new_tags}

    result = await do_request(
        session,
        'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
        request_type='PATCH',
        post_data=patch_params,
        expected_code=200,
    )

    assert new_title == result['name']
    assert new_tags == result['category']
    with db_session:
        chan = session.mds.ChannelMetadata.get_my_channels().first()
        assert chan.status == UPDATED
        assert chan.tags == new_tags
        assert chan.title == new_title


@pytest.mark.asyncio
async def test_get_entry(enable_chant, enable_api, session):
    """
    Test getting an entry with REST API GET request
    """
    with db_session:
        chan = session.mds.TorrentMetadata(
            title="bla", infohash=random_infohash(), tracker_info="http://sometracker.local/announce"
        )
        chan.status = COMMITTED
    await do_request(
        session,
        'metadata/%s/%i' % (hexlify(chan.public_key), chan.id_),
        expected_json=chan.to_simple_dict(include_trackers=True),
    )


@pytest.mark.asyncio
async def test_get_entry_not_found(enable_chant, enable_api, session):
    """
    Test trying to get a non-existing entry with the REST API GET request
    """
    await do_request(session, 'metadata/%s/%i' % (hexlify(b"0" * 64), 123), expected_code=404)


@pytest.mark.asyncio
async def test_check_torrent_health(enable_chant, enable_api, session, mock_dlmgr, udp_tracker):
    """
    Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
    """
    infohash = b'a' * 20
    tracker_url = 'udp://localhost:%s/announce' % udp_tracker.port
    udp_tracker.tracker_info.add_info_about_infohash(infohash, 12, 11, 1)

    with db_session:
        tracker_state = session.mds.TrackerState(url=tracker_url)
        torrent_state = session.mds.TorrentState(trackers=tracker_state, infohash=infohash)
        session.mds.TorrentMetadata(
            infohash=infohash, title='ubuntu-torrent.iso', size=42, tracker_info=tracker_url, health=torrent_state
        )
    url = 'metadata/torrents/%s/health?timeout=%s&refresh=1' % (hexlify(infohash), TORRENT_CHECK_TIMEOUT)

    # Initialize the torrent checker
    session.torrent_checker = TorrentChecker(session)
    await session.torrent_checker.initialize()

    # Add mock DHT response - we both need to account for the case when BEP33 is used and the old lookup method
    session.dlmgr.get_metainfo = lambda _, **__: succeed(None)
    dht_health_dict = {"infohash": hexlify(infohash), "seeders": 1, "leechers": 2}
    session.dlmgr.dht_health_manager.get_health = lambda *_, **__: succeed({"DHT": [dht_health_dict]})

    # Left for compatibility with other tests in this object
    await udp_tracker.start()
    json_response = await do_request(session, url)
    assert "health" in json_response
    assert "udp://localhost:%s" % udp_tracker.port in json_response['health']
    if has_bep33_support():
        assert "DHT" in json_response['health']

    json_response = await do_request(session, url + '&nowait=1')
    assert json_response == {'checking': '1'}


@pytest.mark.asyncio
async def test_check_torrent_query(enable_chant, enable_api, session, udp_tracker):
    """
    Test that the endpoint responds with an error message if the timeout parameter has a wrong value
    """
    infohash = b'a' * 20
    await do_request(session, "metadata/torrents/%s/health?timeout=wrong_value&refresh=1" % infohash,
                     expected_code=400)
