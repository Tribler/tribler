import uuid
from unittest.mock import Mock

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from pony.orm import db_session

from tribler.core.components.gigachannel.community.gigachannel_community import ChannelsPeersMapping
from tribler.core.components.metadata_store.restapi.remote_query_endpoint import RemoteQueryEndpoint
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash


# pylint: disable=unused-argument,redefined-outer-name,multiple-statements


@pytest.fixture
def mock_gigachannel_community():
    return Mock()


@pytest.fixture
def endpoint(metadata_store, mock_gigachannel_community):
    return RemoteQueryEndpoint(mock_gigachannel_community, metadata_store)


async def test_create_remote_search_request(rest_api, mock_gigachannel_community):
    """
    Test that remote search call is sent on a REST API search request
    """
    sent = {}
    peers = []
    request_uuid = uuid.uuid4()

    def mock_send(**kwargs):
        sent.update(kwargs)
        return request_uuid, peers

    # Test querying for keywords
    mock_gigachannel_community.send_search_request = mock_send
    search_txt = "foo"
    await do_request(
        rest_api,
        f'remote_query?txt_filter={search_txt}',
        request_type="PUT",
        expected_code=200,
        expected_json={"request_uuid": str(request_uuid), "peers": peers},
    )
    assert sent['txt_filter'] == search_txt
    sent.clear()

    # Test querying channel data by public key, e.g. for channel preview purposes
    channel_pk = "ff"
    await do_request(
        rest_api, f'remote_query?channel_pk={channel_pk}&metadata_type=torrent', request_type="PUT", expected_code=200
    )
    assert hexlify(sent['channel_pk']) == channel_pk


async def test_get_channels_peers(rest_api, metadata_store, mock_gigachannel_community):
    """
    Test getting debug info about the state of channels to peers mapping
    """

    mapping = mock_gigachannel_community.channels_peers = ChannelsPeersMapping()

    peer_key = default_eccrypto.generate_key("curve25519")
    chan_key = default_eccrypto.generate_key("curve25519")
    with db_session:
        chan = metadata_store.ChannelMetadata(sign_with=chan_key, name="bla", infohash=random_infohash())

    peer = Peer(peer_key, ("1.2.3.4", 5))
    mapping.add(peer, chan.public_key, chan.id_)

    result = await do_request(
        rest_api,
        'remote_query/channels_peers',
        request_type="GET",
        expected_code=200,
    )
    first_result = result["channels_list"][0]
    assert first_result["channel_name"] == chan.title
    assert first_result["channel_pk"] == hexlify(chan.public_key)
    assert first_result["channel_id"] == chan.id_
    assert first_result["peers"][0][0] == hexlify(peer.mid)
