from __future__ import annotations

from binascii import hexlify, unhexlify
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Integer, List, String
from typing_extensions import Self

from tribler.core.database.restapi.schema import MetadataParameters
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from aiohttp.abc import Request
    from multidict import MultiMapping

    from tribler.core.content_discovery.community import ContentDiscoveryCommunity


class RemoteQueryParameters(MetadataParameters):
    """
    The REST API schema for requets to other peers.
    """

    uuid = String()
    channel_pk = String(description="Channel to query, must also define origin_id")
    origin_id = Integer(default=None, description="Peer id to query, must also define channel_pk")


class SearchEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database.
    """

    path = "/search"

    def __init__(self,
                 content_discovery_community: ContentDiscoveryCommunity,
                 middlewares: tuple = (),
                 client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new search endpoint.
        """
        super().__init__(middlewares, client_max_size)
        self.content_discovery_community = content_discovery_community
        self.app.add_routes([web.put("/remote", self.remote_search)])

    @classmethod
    def sanitize_parameters(cls: type[Self], parameters: MultiMapping[str]) -> dict:
        """
        Correct the human-readable parameters to be their respective correct type.
        """
        sanitized = dict(parameters)
        if "max_rowid" in parameters:
            sanitized["max_rowid"] = int(parameters["max_rowid"])
        if "channel_pk" in parameters:
            sanitized["channel_pk"] = unhexlify(parameters["channel_pk"])
        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])
        return sanitized

    @docs(
        tags=["Metadata"],
        summary="Perform a search for a given query.",
        responses={
            200: {
                "schema": schema(RemoteSearchResponse={"request_uuid": String(), "peers": List(String())}),
                "examples": {
                    "Success": {
                        "request_uuid": "268560c0-3f28-4e6e-9d85-d5ccb0269693",
                        "peers": ["50e9a2ce646c373985a8e827e328830e053025c6",
                                  "107c84e5d9636c17b46c88c3ddb54842d80081b0"]
                    }
                }
            }
        },
    )
    @querystring_schema(RemoteQueryParameters)
    async def remote_search(self, request: Request) -> RESTResponse:
        """
        Perform a search for a given query.
        """
        self._logger.info("Create remote search request")
        # Results are returned over the Events endpoint.
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError) as e:
            return RESTResponse({"error": f"Error processing request parameters: {e}"}, status=HTTP_BAD_REQUEST)
        self._logger.info("Parameters: %s", str(sanitized))

        request_uuid, peers_list = self.content_discovery_community.send_search_request(**sanitized)
        peers_mid_list = [hexlify(p.mid).decode() for p in peers_list]

        return RESTResponse({"request_uuid": str(request_uuid), "peers": peers_mid_list})
