from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp_apispec import docs, json_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Integer, List, Nested, String

from tribler.core.restapi.rest_endpoint import MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from tribler.core.recommender.manager import Manager
    from tribler.core.restapi.rest_manager import TriblerRequest

    RequestType: TypeAlias = TriblerRequest[tuple[Manager]]


class RecommenderEndpoint(RESTEndpoint):
    """
    This is the top-level endpoint class that allows the GUI to communicate what has been clicked by a user.
    """

    path = "/api/recommender"

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new database endpoint.
        """
        super().__init__(middlewares, client_max_size)

        self.manager: Manager | None = None
        self.required_components = ("manager", )

        self.app.add_routes([web.put("/clicked", self.put_clicked)])

    @docs(
        tags=["Recommender"],
        summary="Set the preference relationship between infohashes.",
        parameters=[],
        responses={
            200: {
                "schema": schema(ClickedResponse={"added": Boolean}),
                "examples": {"added": True}
            }
        }
    )
    @json_schema(schema(ClickedRequest={
        "query": (String, "The query that led to the list of results"),
        "chosen_index": (String, "The winning result index in the results list"),
        "timestamp": (Integer, "The timestamp of the query"),
        "results": (List(Nested(schema(ClickedResult={"infohash": (String, "A displayed infohash"),
                                                      "seeders": (Integer, "Its displayed number of seeders"),
                                                      "leechers": (Integer, "Its displayed number of seeders")}))),
                    "The displayed infohashes"),
    }))
    async def put_clicked(self, request: RequestType) -> RESTResponse:
        """
        The user has clicked one infohash over others.

        We expect the format:

        .. code-block::

            {
                query: str,
                chosen_index: int,
                timestamp: int,
                results: list[{
                    infohash: str,
                    seeders: int,
                    leechers: int
                }]
            }

        :param request: the user request.
        :returns: the REST response.
        """
        parameters = await request.text()

        request.context[0].add_query(parameters)

        return RESTResponse({"added": True})
