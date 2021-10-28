import binascii
from binascii import unhexlify
from typing import Optional, Set, Tuple

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean, List, String

from pony.orm import db_session

from tribler_common.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH

from tribler_core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse
from tribler_core.components.restapi.rest.schema import HandledErrorSchema
from tribler_core.components.tag.community.tag_community import TagCommunity
from tribler_core.components.tag.community.tag_payload import TagOperation
from tribler_core.components.tag.db.tag_db import TagDatabase, TagOperationEnum
from tribler_core.utilities.utilities import froze_it


@froze_it
class TagsEndpoint(RESTEndpoint):
    """
    Top-level endpoint for tags.
    """

    def __init__(self, *args, **kwargs):
        RESTEndpoint.__init__(self, *args, **kwargs)
        self.db: Optional[TagDatabase] = None
        self.community: Optional[TagCommunity] = None

    @staticmethod
    def validate_infohash(infohash: str) -> Tuple[bool, Optional[RESTResponse]]:
        try:
            infohash = unhexlify(infohash)
            if len(infohash) != 20:
                return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)
        except binascii.Error:
            return False, RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)

        return True, None

    def setup_routes(self):
        self.app.add_routes(
            [
                web.patch('/{infohash}', self.update_tags_entries),
                web.get('/{infohash}/suggestions', self.get_suggestions),
            ]
        )

    @docs(
        tags=["General"],
        summary="Update a particular torrent with tags.",
        responses={
            200: {
                "schema": schema(UpdateTagsResponse={'success': Boolean()})
            },
            HTTP_BAD_REQUEST: {
                "schema": HandledErrorSchema, 'example': {"error": "Invalid tag length"}},
        },
        description="This endpoint updates a particular torrent with the provided tags."
    )
    async def update_tags_entries(self, request):
        params = await request.json()
        infohash = request.match_info["infohash"]
        ih_valid, error_response = TagsEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        tags = {tag.lower() for tag in params["tags"]}

        # Validate whether the size of the tag is within the allowed range
        for tag in tags:
            if len(tag) < MIN_TAG_LENGTH or len(tag) > MAX_TAG_LENGTH:
                return RESTResponse({"error": "Invalid tag length"}, status=HTTP_BAD_REQUEST)

        self.modify_tags(unhexlify(infohash), tags)

        return RESTResponse({"success": True})

    @db_session
    def modify_tags(self, infohash: bytes, new_tags: Set[str]):
        """
        Modify the tags of a particular content item.
        """
        if not self.db or not self.community:
            return

        # First, get the current tags and compute the diff between the old and new tags
        old_tags = set(self.db.get_tags(infohash))
        added_tags = new_tags - old_tags
        removed_tags = old_tags - new_tags

        # Create individual tag operations for the added/removed tags
        public_key = self.community.my_peer.key.pub().key_to_bin()
        for tag in added_tags.union(removed_tags):
            type_of_operation = TagOperationEnum.ADD if tag in added_tags else TagOperationEnum.REMOVE
            operation = TagOperation(infohash=infohash, operation=type_of_operation, clock=0,
                                     creator_public_key=public_key, tag=tag)
            operation.clock = self.db.get_clock(operation) + 1
            signature = self.community.sign(operation)
            self.db.add_tag_operation(operation, signature, is_local_peer=True)

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
        ih_valid, error_response = TagsEndpoint.validate_infohash(infohash)
        if not ih_valid:
            return error_response

        with db_session:
            suggestions = [] if self.db is None else self.db.get_suggestions(unhexlify(infohash))
            return RESTResponse({"suggestions": suggestions})
