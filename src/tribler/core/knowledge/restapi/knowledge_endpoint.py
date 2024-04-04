import binascii
from typing import Optional, Tuple

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow import Schema
from marshmallow.fields import Boolean, List, String
from pony.orm import db_session

from tribler.core.database.layers.knowledge import Operation, ResourceType
from tribler.core.database.tribler_database import TriblerDatabase
from tribler.core.knowledge.community import KnowledgeCommunity, is_valid_resource
from tribler.core.knowledge.payload import StatementOperation
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse


class HandledErrorSchema(Schema):
    error = String(description='Optional field describing any failures that may have occurred', required=True)


class KnowledgeEndpoint(RESTEndpoint):
    """
    Top-level endpoint for knowledge management.
    """
    path = '/knowledge'

    def __init__(self, db: TriblerDatabase, community: KnowledgeCommunity):
        super().__init__()
        self.db: TriblerDatabase = db
        self.community: KnowledgeCommunity = community
        self.app.add_routes(
            [
                web.patch('/{infohash}', self.update_knowledge_entries),
                web.get('/{infohash}/tag_suggestions', self.get_tag_suggestions),
            ]
        )

    @staticmethod
    def validate_infohash(infohash: bytes) -> Tuple[bool, Optional[RESTResponse]]:
        try:
            if len(infohash) != 40:
                return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)
        except binascii.Error:
            return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)

        return True, None

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

        # Validate whether the size of the tag is within the allowed range and filter out duplicate tags.
        statements = []
        self._logger.info(f'Statements about {infohash}: {params["statements"]}')
        for statement in params["statements"]:
            obj = statement["object"]
            if not is_valid_resource(obj):
                return RESTResponse({"error": "Invalid tag length"}, status=HTTP_BAD_REQUEST)

            statements.append(statement)

        self.modify_statements(infohash, statements)

        return RESTResponse({"success": True})

    @db_session
    def modify_statements(self, infohash: str, statements: list):
        """
        Modify the statements of a particular content item.
        """
        if not self.community:
            return

        # First, get the current statements and compute the diff between the old and new statements
        old_statements = self.db.knowledge.get_statements(subject_type=ResourceType.TORRENT, subject=infohash)
        old_statements = {(stmt.predicate, stmt.object) for stmt in old_statements}
        self._logger.info(f'Old statements: {old_statements}')
        new_statements = {(stmt["predicate"], stmt["object"]) for stmt in statements}
        self._logger.info(f'New statements: {new_statements}')
        added_statements = new_statements - old_statements
        removed_statements = old_statements - new_statements

        # Create individual statement operations for the added/removed statements
        public_key = self.community.key.pub().key_to_bin()
        for stmt in added_statements.union(removed_statements):
            predicate, obj = stmt
            type_of_operation = Operation.ADD if stmt in added_statements else Operation.REMOVE
            operation = StatementOperation(subject_type=ResourceType.TORRENT, subject=infohash,
                                           predicate=predicate,
                                           object=obj, operation=type_of_operation, clock=0,
                                           creator_public_key=public_key)
            operation.clock = self.db.knowledge.get_clock(operation) + 1
            signature = self.community.sign(operation)
            self.db.knowledge.add_operation(operation, signature, is_local_peer=True)

        self._logger.info(f'Added statements: {added_statements}')
        self._logger.info(f'Removed statements: {removed_statements}')

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
    async def get_tag_suggestions(self, request):
        """
        Get suggested tags for a particular torrent
        """
        infohash = request.match_info["infohash"]
        ih_valid, error_response = KnowledgeEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        with db_session:
            suggestions = self.db.knowledge.get_suggestions(subject=infohash, predicate=ResourceType.TAG)
            return RESTResponse({"suggestions": suggestions})
