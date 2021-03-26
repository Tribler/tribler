import uuid
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.community.gigachannel_community import ChannelsPeersMapping
from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.random_utils import random_infohash
from tribler_core.utilities.unicode import hexlify

# pylint: disable=unused-argument


@pytest.mark.asyncio
async def test_create_remote_search_request(enable_chant, enable_api, session):
    """
    Test that remote search call is sent on a REST API search request
    """
    sent = {}
    request_uuid = uuid.uuid4()

    def mock_send(**kwargs):
        sent.update(kwargs)
        return request_uuid

    # Test querying for keywords
    session.gigachannel_community = Mock()
    session.gigachannel_community.send_search_request = mock_send
    search_txt = "foo"
    await do_request(
        session,
        f'remote_query?txt_filter={search_txt}',
        request_type="PUT",
        expected_code=200,
        expected_json={"request_uuid": str(request_uuid)},
    )
    assert sent['txt_filter'] == search_txt
    sent.clear()

    # Test querying channel data by public key, e.g. for channel preview purposes
    channel_pk = "ff"
    await do_request(
        session, f'remote_query?channel_pk={channel_pk}&metadata_type=torrent', request_type="PUT", expected_code=200
    )
    assert sent['channel_pk'] == channel_pk


@pytest.mark.asyncio
async def test_get_channels_peers(enable_chant, enable_api, session):
    """
    Test getting debug info about the state of channels to peers mapping
    """

    session.gigachannel_community = Mock()
    mapping = session.gigachannel_community.channels_peers = ChannelsPeersMapping()

    peer_key = default_eccrypto.generate_key("curve25519")
    chan_key = default_eccrypto.generate_key("curve25519")
    with db_session:
        chan = session.mds.ChannelMetadata(sign_with=chan_key, name="bla", infohash=random_infohash())

    peer = Peer(peer_key, ("1.2.3.4", 5))
    mapping.add(peer, chan.public_key, chan.id_, chan.timestamp)

    result = await do_request(
        session,
        'remote_query/channels_peers',
        request_type="GET",
        expected_code=200,
    )
    first_result = result["channels_list"][0]
    assert first_result["channel_name"] == chan.title
    assert first_result["channel_pk"] == hexlify(chan.public_key)
    assert first_result["channel_id"] == chan.id_
    assert first_result["peers"][0][0] == hexlify(peer.mid)
