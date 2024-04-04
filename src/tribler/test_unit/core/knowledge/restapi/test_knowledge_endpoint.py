from unittest.mock import Mock

from aiohttp.web_urldispatcher import UrlMappingMatchInfo
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network
from ipv8.test.base import TestBase
from ipv8.test.mocking.endpoint import AutoMockEndpoint

from tribler.core.database.layers.knowledge import ResourceType
from tribler.core.knowledge.community import KnowledgeCommunity, KnowledgeCommunitySettings
from tribler.core.knowledge.payload import StatementOperation
from tribler.core.knowledge.restapi.knowledge_endpoint import KnowledgeEndpoint
from tribler.test_unit.base_restapi import MockRequest, response_to_json


class MockCommunity(KnowledgeCommunity):
    """
    An inert KnowledgeCommunity.
    """

    community_id = b"\x00" * 20

    def __init__(self, settings: KnowledgeCommunitySettings) -> None:
        """
        Create a new MockCommunity.
        """
        super().__init__(settings)
        self.cancel_all_pending_tasks()

    def sign(self, operation: StatementOperation) -> bytes:
        """
        Fake a signature.
        """
        return b""


class UpdateKnowledgeEntriesRequest(MockRequest):
    """
    A MockRequest that mimics UpdateKnowledgeEntriesRequests.
    """

    def __init__(self, query: dict, infohash: str) -> None:
        """
        Create a new UpdateKnowledgeEntriesRequest.
        """
        super().__init__(query, "PATCH", f"/knowledge/{infohash}")
        self._infohash = infohash

    async def json(self) -> dict:
        """
        Get the json equivalent of the query (i.e., just the query).
        """
        return self._query

    @property
    def match_info(self) -> UrlMappingMatchInfo:
        """
        Get the match info (the infohash in the url).
        """
        return UrlMappingMatchInfo({"infohash": self._infohash}, Mock())


class GetTagSuggestionsRequest(MockRequest):
    """
    A MockRequest that mimics GetTagSuggestionsRequests.
    """

    def __init__(self, infohash: str) -> None:
        """
        Create a new GetTagSuggestionsRequest.
        """
        super().__init__({}, "GET", f"/knowledge/{infohash}/tag_suggestions")
        self._infohash = infohash

    @property
    def match_info(self) -> UrlMappingMatchInfo:
        """
        Get the match info (the infohash in the url).
        """
        return UrlMappingMatchInfo({"infohash": self._infohash}, Mock())


class TestKnowledgeEndpoint(TestBase):
    """
    Tests for the KnowledgeEndpoint REST endpoint.
    """

    def setUp(self) -> None:
        """
        Create a new endpoint and a mock community.
        """
        super().setUp()
        key = default_eccrypto.generate_key("curve25519")
        settings = KnowledgeCommunitySettings(
            endpoint=AutoMockEndpoint(),
            my_peer=Peer(key),
            network=Network(),
            key=key,
            db=Mock()
        )
        self.endpoint = KnowledgeEndpoint(settings.db, MockCommunity(settings))

    def tag_to_statement(self, tag: str) -> dict:
        """
        Convert a tag to a statement dictionary.
        """
        return {"predicate": ResourceType.TAG, "object": tag}

    async def test_add_tag_invalid_infohash(self) -> None:
        """
        Test if an error is returned if we try to add a tag to content with an invalid infohash.
        """
        post_data = {"knowledge": [self.tag_to_statement("abc"), self.tag_to_statement("def")]}

        response = await self.endpoint.update_knowledge_entries(UpdateKnowledgeEntriesRequest(post_data, "3f3"))
        response_body_json = await response_to_json(response)

        self.assertEqual(400, response.status)
        self.assertEqual("Invalid infohash", response_body_json["error"])

    async def test_add_invalid_tag_too_short(self) -> None:
        """
        Test whether an error is returned if we try to add a tag that is too short or long.
        """
        post_data = {"statements": [self.tag_to_statement("a")]}

        response = await self.endpoint.update_knowledge_entries(UpdateKnowledgeEntriesRequest(post_data, "a" * 40))
        response_body_json = await response_to_json(response)

        self.assertEqual(400, response.status)
        self.assertEqual("Invalid tag length", response_body_json["error"])

    async def test_add_invalid_tag_too_long(self) -> None:
        """
        Test whether an error is returned if we try to add a tag that is too short or long.
        """
        post_data = {"statements": [self.tag_to_statement("a" * 60)]}

        response = await self.endpoint.update_knowledge_entries(UpdateKnowledgeEntriesRequest(post_data, "a" * 40))
        response_body_json = await response_to_json(response)

        self.assertEqual(400, response.status)
        self.assertEqual("Invalid tag length", response_body_json["error"])

    async def test_modify_tags(self) -> None:
        """
        Test modifying tags.
        """
        post_data = {"statements": [self.tag_to_statement("abc"), self.tag_to_statement("def")]}
        self.endpoint.db.knowledge.get_statements = Mock(return_value=[])
        self.endpoint.db.knowledge.get_clock = Mock(return_value=0)

        response = await self.endpoint.update_knowledge_entries(UpdateKnowledgeEntriesRequest(post_data, "a" * 40))
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["success"])

    async def test_modify_tags_no_community(self) -> None:
        """
        Test if the KnowledgeEndpoint can function without a community.
        """
        self.endpoint.community = None
        post_data = {"statements": [self.tag_to_statement("abc"), self.tag_to_statement("def")]}
        self.endpoint.db.knowledge.get_statements = Mock(return_value=[])
        self.endpoint.db.knowledge.get_clock = Mock(return_value=0)

        response = await self.endpoint.update_knowledge_entries(UpdateKnowledgeEntriesRequest(post_data, "a" * 40))
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["success"])

    async def test_get_suggestions_invalid_infohash(self) -> None:
        """
        Test if an error is returned if we fetch suggestions from content with an invalid infohash.
        """
        response = await self.endpoint.get_tag_suggestions(GetTagSuggestionsRequest("3f3"))
        response_body_json = await response_to_json(response)

        self.assertEqual(400, response.status)
        self.assertEqual("Invalid infohash", response_body_json["error"])

    async def test_get_suggestions(self) -> None:
        """
        Test if we can successfully fetch suggestions from content.
        """
        self.endpoint.db.knowledge.get_suggestions = Mock(return_value=["test"])

        response = await self.endpoint.get_tag_suggestions(GetTagSuggestionsRequest("a" * 40))
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(["test"], response_body_json["suggestions"])
