from __future__ import annotations

import binascii
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow import Schema
from marshmallow.fields import Boolean, List, String
from pony.orm import db_session
from typing_extensions import TypeAlias

from tribler.core.database.layers.knowledge import Operation, ResourceType
from tribler.core.knowledge.community import KnowledgeCommunity, is_valid_resource
from tribler.core.knowledge.payload import StatementOperation
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from tribler.core.database.tribler_database import TriblerDatabase
    from tribler.core.restapi.rest_manager import TriblerRequest

    RequestType: TypeAlias = TriblerRequest[tuple[TriblerDatabase, KnowledgeCommunity]]


class HandledErrorSchema(Schema):
    """
    The REST schema for knowledge errors.
    """

    error = String(description="Optional field describing any failures that may have occurred", required=True)


class KnowledgeEndpoint(RESTEndpoint):
    """
    Top-level endpoint for knowledge management.
    """

    path = "/api/knowledge"

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new knowledge endpoint.
        """
        super().__init__(middlewares, client_max_size)

        self.db: TriblerDatabase | None = None
        self.required_components = ("db", )

        self.community: KnowledgeCommunity | None = None

        self.app.add_routes(
            [
                web.patch("/{infohash}", self.update_knowledge_entries),
                web.get("/{infohash}/tag_suggestions", self.get_tag_suggestions),
            ]
        )

    @staticmethod
    def validate_infohash(infohash: str) -> tuple[bool, RESTResponse | None]:
        """
        Check if the given bytes are a string of 40 HEX-character bytes.
        """
        try:
            if len(infohash) != 40:
                return False, RESTResponse({"error": {
                                                "handled": True,
                                                "message": "Invalid infohash"
                                            }}, status=HTTP_BAD_REQUEST)
        except binascii.Error:
            return False, RESTResponse({"error": {
                                            "handled": True,
                                            "message": "Invalid infohash"
                                        }}, status=HTTP_BAD_REQUEST)

        return True, None

    @docs(
        tags=["General"],
        summary="Update the metadata associated with a particular torrent.",
        responses={
            200: {
                "schema": schema(UpdateTagsResponse={"success": Boolean()})
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema, "example": {"error": {"handled": True, "message": "Invalid tag length"}}
            }
        },
        description="This endpoint updates a particular torrent with the provided metadata."
    )
    async def update_knowledge_entries(self, request: RequestType) -> RESTResponse:
        """
        Update the metadata associated with a particular torrent.
        """
        params = await request.json()
        infohash = request.match_info["infohash"]
        ih_valid, error_response = KnowledgeEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        # Validate whether the size of the tag is within the allowed range and filter out duplicate tags.
        statements = []
        self._logger.info("Statements about %s: %s", infohash, str(params["statements"]))
        for statement in params["statements"]:
            obj = statement["object"]
            if not is_valid_resource(obj):
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "Invalid tag length"
                                    }}, status=HTTP_BAD_REQUEST)

            statements.append(statement)

        self.modify_statements(request.context[0], infohash, statements)

        return RESTResponse({"success": True})

    @db_session
    def modify_statements(self, db: TriblerDatabase, infohash: str, statements: list) -> None:
        """
        Modify the statements of a particular content item.
        """
        if not self.community:
            return

        # First, get the current statements and compute the diff between the old and new statements
        old_statements = db.knowledge.get_statements(subject_type=ResourceType.TORRENT, subject=infohash)
        old_statements = {(stmt.predicate, stmt.object) for stmt in old_statements}
        self._logger.info("Old statements: %s", old_statements)
        new_statements = {(stmt["predicate"], stmt["object"]) for stmt in statements}
        self._logger.info("New statements: %s", new_statements)
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
            operation.clock = db.knowledge.get_clock(operation) + 1
            signature = self.community.sign(operation)
            db.knowledge.add_operation(operation, signature, is_local_peer=True)

        self._logger.info("Added statements: %s", added_statements)
        self._logger.info("Removed statements: %s", removed_statements)

    @docs(
        tags=["General"],
        summary="Get tag suggestions for a torrent with a particular infohash.",
        responses={
            200: {
                "schema": schema(SuggestedTagsResponse={"suggestions": List(String)})
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema, "example": {"error": {"handled": True, "message": "Invalid infohash"}}
            }
        },
        description="This endpoint updates a particular torrent with the provided tags."
    )
    async def get_tag_suggestions(self, request: RequestType) -> RESTResponse:
        """
        Get suggested tags for a particular torrent.
        """
        infohash = request.match_info["infohash"]
        ih_valid, error_response = KnowledgeEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        with db_session:
            suggestions = request.context[0].knowledge.get_suggestions(subject=infohash, predicate=ResourceType.TAG)
            return RESTResponse({"suggestions": suggestions})
