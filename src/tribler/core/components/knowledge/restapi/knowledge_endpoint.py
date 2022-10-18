import binascii
from typing import Optional, Set, Tuple

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, List, String
from pony.orm import db_session

from tribler.core.components.knowledge.community.knowledge_community import KnowledgeCommunity
from tribler.core.components.knowledge.community.knowledge_payload import StatementOperation
from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase, Operation, ResourceType
from tribler.core.components.knowledge.knowledge_constants import MAX_RESOURCE_LENGTH, MIN_RESOURCE_LENGTH
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse
from tribler.core.components.restapi.rest.schema import HandledErrorSchema
from tribler.core.utilities.utilities import froze_it


@froze_it
class KnowledgeEndpoint(RESTEndpoint):
    """
    Top-level endpoint for knowledge management.
    """

    def __init__(self, db: KnowledgeDatabase, community: KnowledgeCommunity):
        super().__init__()
        self.db: KnowledgeDatabase = db
        self.community: KnowledgeCommunity = community

    @staticmethod
    def validate_infohash(infohash: bytes) -> Tuple[bool, Optional[RESTResponse]]:
        try:
            if len(infohash) != 40:
                return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)
        except binascii.Error:
            return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)

        return True, None

    def setup_routes(self):
        self.app.add_routes(
            [
                web.patch('/{infohash}', self.update_knowledge_entries),
                web.get('/{infohash}/suggestions', self.get_suggestions),
            ]
        )

    @docs(
        tags=["General"],
        summary="Update the metadata associated with a particular torrent.",
        responses={
            200: {
                "schema": schema(UpdateTagsResponse={'success': Boolean()})
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema, 'example': {"error": "Invalid tag length"}},
        },
        description="This endpoint updates a particular torrent with the provided metadata."
    )
    async def update_knowledge_entries(self, request):
        params = await request.json()
        infohash = request.match_info["infohash"]
        ih_valid, error_response = KnowledgeEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        # Validate whether the size of the tag is within the allowed range
        tags = set(params["tags"])
        for tag in tags:
            if len(tag) < MIN_RESOURCE_LENGTH or len(tag) > MAX_RESOURCE_LENGTH:
                return RESTResponse({"error": "Invalid tag length"}, status=HTTP_BAD_REQUEST)

        self.modify_tags(infohash, tags)

        return RESTResponse({"success": True})

    @db_session
    def modify_tags(self, infohash: str, new_tags: Set[str]):
        """
        Modify the tags of a particular content item.
        """
        if not self.community:
            return

        # First, get the current tags and compute the diff between the old and new tags
        old_tags = set(self.db.get_objects(infohash, predicate=ResourceType.TAG))
        added_tags = new_tags - old_tags
        removed_tags = old_tags - new_tags

        # Create individual tag operations for the added/removed tags
        public_key = self.community.key.pub().key_to_bin()
        for tag in added_tags.union(removed_tags):
            type_of_operation = Operation.ADD if tag in added_tags else Operation.REMOVE
            operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=infohash,
                                           predicate=ResourceType.TAG,
                                           object=tag, operation=type_of_operation, clock=0,
                                           creator_public_key=public_key)
            operation.clock = self.db.get_clock(operation) + 1
            signature = self.community.sign(operation)
            self.db.add_operation(operation, signature, is_local_peer=True)

    @docs(
        tags=["General"],
        summary="Get tag suggestions for a torrent with a particular infohash.",
        responses={
            200: {
                "schema": schema(SuggestedTagsResponse={'suggestions': List(String)})
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema, 'example': {"error": "Invalid infohash"}},
        },
        description="This endpoint updates a particular torrent with the provided tags."
    )
    async def get_suggestions(self, request):
        """
        Get suggestions for a particular tag.
        """
        infohash = request.match_info["infohash"]
        ih_valid, error_response = KnowledgeEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        with db_session:
            suggestions = self.db.get_suggestions(infohash, predicate=ResourceType.TAG)
            return RESTResponse({"suggestions": suggestions})
