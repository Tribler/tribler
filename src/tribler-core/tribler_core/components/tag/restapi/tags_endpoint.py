import binascii
from binascii import unhexlify
from typing import Optional, Set

from aiohttp import web
from aiohttp_apispec import docs
from marshmallow.fields import Boolean
from pony.orm import db_session

from ipv8.REST.schema import schema
from tribler_common.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH
from tribler_core.components.tag.community.tag_community import TagCommunity
from tribler_core.components.tag.community.tag_payload import TagOperation
from tribler_core.components.tag.db.tag_db import TagDatabase, TagOperationEnum
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse
from tribler_core.restapi.schema import HandledErrorSchema
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

    def setup_routes(self):
        self.app.add_routes(
            [
                web.patch('/{infohash}', self.update_tags_entries),
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
        try:
            infohash = unhexlify(request.match_info['infohash'])
            if len(infohash) != 20:
                return RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)
        except binascii.Error:
            return RESTResponse({"error": "Invalid infohash"}, status=HTTP_BAD_REQUEST)

        tags = {tag.lower() for tag in params["tags"]}

        # Validate whether the size of the tag is within the allowed range
        for tag in tags:
            if len(tag) < MIN_TAG_LENGTH or len(tag) > MAX_TAG_LENGTH:
                return RESTResponse({"error": "Invalid tag length"}, status=HTTP_BAD_REQUEST)

        self.modify_tags(infohash, tags)

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
            operation = TagOperationEnum.ADD if tag in added_tags else TagOperationEnum.REMOVE
            counter = self.db.get_next_operation_counter()
            operation = TagOperation(infohash=infohash, operation=operation, timestamp=counter,
                                     creator_public_key=public_key, tag=tag)
            signature = self.community.sign(operation)
            self.db.add_tag_operation(operation, signature, is_local_peer=True)
