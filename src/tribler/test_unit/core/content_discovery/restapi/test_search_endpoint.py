from __future__ import annotations

from uuid import UUID

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network
from ipv8.test.base import TestBase
from ipv8.test.mocking.endpoint import AutoMockEndpoint
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.content_discovery.community import ContentDiscoveryCommunity
from tribler.core.content_discovery.restapi.search_endpoint import SearchEndpoint
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST


class MockContentDiscoveryCommunity(ContentDiscoveryCommunity):
    """
    A mocked ContentDiscoveryCommunity.
    """

    def __init__(self) -> None:
        """
        Create a new mocked ContentDiscoveryCommunity.
        """
        my_peer = Peer(LibNaCLSK(b"\x01" * 64))
        super().__init__(self.settings_class(my_peer=my_peer, endpoint=AutoMockEndpoint(), network=Network()))

    def send_search_request(self, **kwargs) -> tuple[UUID, list[Peer]]:
        """
        Fake the return values of a search request.
        """
        return UUID(int=1), [self.my_peer]


class TestSearchEndpoint(TestBase):
    """
    Tests for the SearchEndpoint REST endpoint.
    """

    async def test_remote_search_bad_request(self) -> None:
        """
        Test if a bad request returns the bad request status.
        """
        endpoint = SearchEndpoint()
        request = MockRequest("/api/search/remote", "PUT", {"channel_pk": "GG"})
        request.context = [MockContentDiscoveryCommunity()]

        response = await endpoint.remote_search(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_remote_search(self) -> None:
        """
        Test if a good search request returns a dict with the UUID and serving peers.
        """
        endpoint = SearchEndpoint()
        request = MockRequest("/api/search/remote", "PUT", {"channel_pk": "AA", "fts_text": ""})
        request.context = [MockContentDiscoveryCommunity()]

        response = await endpoint.remote_search(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("00000000-0000-0000-0000-000000000001", response_body_json["request_uuid"])
        self.assertEqual(["5b16b30807cdcb11f8214a5eb762c0dc1931c503"], response_body_json["peers"])
