from __future__ import annotations

import asyncio
import json
import typing
from binascii import unhexlify

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Integer, String
from pony.orm import db_session
from typing_extensions import Self, TypeAlias

from tribler.core.database.queries import to_fts_query
from tribler.core.database.restapi.schema import MetadataSchema, SearchMetadataParameters, TorrentSchema
from tribler.core.database.serialization import REGULAR_TORRENT
from tribler.core.notifier import Notification
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    MAX_REQUEST_SIZE,
    RESTEndpoint,
    RESTResponse,
)

if typing.TYPE_CHECKING:
    from multidict import MultiDictProxy, MultiMapping

    from tribler.core.database.store import MetadataStore
    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager
    from tribler.core.restapi.rest_manager import TriblerRequest
    from tribler.core.torrent_checker.torrent_checker import TorrentChecker

    RequestType: TypeAlias = TriblerRequest[tuple[MetadataStore]]

TORRENT_CHECK_TIMEOUT = 20

# This dict is used to translate JSON fields into the columns used in Pony for _sorting_.
# id_ is not in the list because there is not index on it, so we never really want to sort on it.
json2pony_columns = {
    "category": "tags",
    "name": "title",
    "size": "size",
    "infohash": "infohash",
    "date": "torrent_date",
    "created": "torrent_date",
    "status": "status",
    "votes": "votes",
    "subscribed": "subscribed",
    "health": "HEALTH",
}


def parse_bool(obj: str) -> bool:
    """
    Parse input to boolean True or False.
    Allow parsing text 'false', 'true' '1', '0' to boolean.

    :param obj: Object to parse
    """
    return bool(json.loads(obj))


class DatabaseEndpoint(RESTEndpoint):
    """
    This is the top-level endpoint class that serves other endpoints.

     /metadata
              /torrents
              /<public_key>
    """

    path = "/api/metadata"

    def __init__(self, middlewares: tuple = (), client_max_size: int = MAX_REQUEST_SIZE) -> None:
        """
        Create a new database endpoint.
        """
        super().__init__(middlewares, client_max_size)

        self.mds: MetadataStore | None = None
        self.required_components = ("mds", )

        self.download_manager: DownloadManager | None = None
        self.torrent_checker: TorrentChecker | None = None

        self.app.add_routes(
            [
                web.get("/torrents/{infohash}/health", self.get_torrent_health),
                web.get("/torrents/popular", self.get_popular_torrents),
                web.get("/search/local", self.local_search),
                web.get("/search/completions", self.completions)
            ]
        )

    @classmethod
    def sanitize_parameters(cls: type[Self],
                            parameters: MultiDictProxy | MultiMapping[str]
                            ) -> dict[str, str | float | list[str] | set[bytes] | bytes | None]:
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized: dict[str, str | float | list[str] | set[bytes] | bytes | None] = {
            "first": int(parameters.get("first", 1)),
            "last": int(parameters.get("last", 50)),
            "sort_by": json2pony_columns.get(parameters.get("sort_by", "")),
            "sort_desc": parse_bool(parameters.get("sort_desc", "true")),
            "hide_xxx": parse_bool(parameters.get("hide_xxx", "false")),
            "category": parameters.get("category"),
        }

        if "tags" in parameters:
            sanitized["tags"] = parameters.getall("tags")
        if "max_rowid" in parameters:
            sanitized["max_rowid"] = int(parameters["max_rowid"])
        if "channel_pk" in parameters:
            sanitized["channel_pk"] = unhexlify(parameters["channel_pk"])
        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])
        if "popular" in parameters and parse_bool(parameters.get("popular", "false")):
            sanitized["sort_by"] = "HEALTH"
        return sanitized

    @docs(
        tags=["Metadata"],
        summary="Fetch the swarm health of a specific torrent.",
        parameters=[
            {
                "in": "path",
                "name": "infohash",
                "description": "Infohash of the download to remove",
                "type": "string",
                "required": True,
            },
            {
                "in": "query",
                "name": "timeout",
                "description": "Timeout to be used in the connections to the trackers",
                "type": "integer",
                "default": 20,
                "required": False,
            },
        ],
        responses={
            200: {
                "schema": schema(
                    HealthCheckResponse={
                        "checking": Boolean()
                    }
                ),
                "examples": [
                    {"checking": 1},
                ],
            }
        },
    )
    async def get_torrent_health(self, request: RequestType) -> RESTResponse:
        """
        Fetch the swarm health of a specific torrent.
        """
        self._logger.info("Get torrent health request: %s", str(request))
        try:
            timeout = int(request.query.get("timeout", TORRENT_CHECK_TIMEOUT))
        except ValueError as e:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": f"Error processing timeout parameter: {e}"
                                }}, status=HTTP_BAD_REQUEST)

        if self.torrent_checker is None:
            return RESTResponse({"checking": False})

        infohash = unhexlify(request.match_info["infohash"])
        health_check_coro = self.torrent_checker.check_torrent_health(infohash, timeout=timeout, scrape_now=True)
        _ = self.register_anonymous_task("health_check", asyncio.ensure_future(health_check_coro))
        return RESTResponse({"checking": True})

    def add_download_progress_to_metadata_list(self, contents_list: list[dict]) -> None:
        """
        Retrieve the download status from libtorrent and attach it to the torrent descriptions in the content list.
        """
        if self.download_manager is not None:
            for torrent in contents_list:
                if torrent["type"] == REGULAR_TORRENT:
                    dl = self.download_manager.get_download(unhexlify(torrent["infohash"]))
                    if dl is not None and dl.tdef.infohash not in self.download_manager.metainfo_requests:
                        torrent["progress"] = dl.get_state().get_progress()

    @docs(
        tags=["Metadata"],
        summary="Get the list of most popular torrents.",
        responses={
            200: {
                "schema": schema(
                    GetPopularTorrentsResponse={
                        "results": [TorrentSchema],
                        "first": Integer(),
                        "last": Integer(),
                    }
                )
            }
        },
    )
    async def get_popular_torrents(self, request: RequestType) -> RESTResponse:
        """
        Get the list of most popular torrents.
        """
        sanitized = self.sanitize_parameters(request.query)
        sanitized["metadata_type"] = REGULAR_TORRENT
        sanitized["popular"] = True
        if t_filter := request.query.get("filter"):
            sanitized["txt_filter"] = t_filter

        with db_session:
            contents_list = [entry.to_simple_dict() for entry in request.context[0].get_entries(**sanitized)]

        self.add_download_progress_to_metadata_list(contents_list)
        response_dict = {
            "results": contents_list,
            "first": sanitized["first"],
            "last": sanitized["last"],
        }

        return RESTResponse(response_dict)

    @docs(
        tags=["Metadata"],
        summary="Perform a search for a given query.",
        responses={
            200: {
                "schema": schema(
                    SearchResponse={
                        "results": [MetadataSchema],
                        "first": Integer(),
                        "last": Integer(),
                        "sort_by": String(),
                        "sort_desc": Integer(),
                        "total": Integer(),
                    }
                )
            }
        },
    )
    @querystring_schema(SearchMetadataParameters)
    async def local_search(self, request: RequestType) -> RESTResponse:
        """
        Perform a search for a given query.
        """
        try:
            sanitized = self.sanitize_parameters(request.query)
        except (ValueError, KeyError):
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "Error processing request parameters"
                                }}, status=HTTP_BAD_REQUEST)

        include_total = request.query.get("include_total", "")
        query = request.query.get("fts_text")
        if query is None:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": f"Got search with no fts_text: {dict(request.query)}"
                                }}, status=HTTP_BAD_REQUEST)
        if t_filter := request.query.get("filter"):
            query += f" {t_filter}"
        fts = to_fts_query(query)
        sanitized["txt_filter"] = fts
        self._logger.info("FTS: %s", fts)

        mds: MetadataStore = request.context[0]

        def search_db() -> tuple[list[dict], int, int]:
            with db_session:
                pony_query = mds.get_entries(**sanitized)
                search_results = [r.to_simple_dict() for r in pony_query]
                if include_total:
                    total = mds.get_total_count(**sanitized)
                    max_rowid = mds.get_max_rowid()
                else:
                    total = max_rowid = None
            if self.download_manager is not None:
                self.download_manager.notifier.notify(Notification.local_query_results,
                                                      query=request.query.get("fts_text"),
                                                      results=list(search_results))
            return search_results, total, max_rowid

        try:
            search_results, total, max_rowid = await mds.run_threaded(search_db)
        except Exception as e:
            self._logger.exception("Error while performing DB search: %s: %s", type(e).__name__, e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

        response_dict = {
            "results": search_results,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": sanitized["sort_desc"],
        }
        if include_total:
            response_dict.update(total=total, max_rowid=max_rowid)

        return RESTResponse(response_dict)

    @docs(
        tags=["Metadata"],
        summary="Return auto-completion suggestions for a given query.",
        parameters=[{"in": "query", "name": "q", "description": "Search query", "type": "string", "required": True}],
        responses={
            200: {
                "schema": schema(
                    CompletionsResponse={
                        "completions": [String],
                    }
                ),
                "examples": {"completions": ["pioneer one", "pioneer movie"]},
            }
        },
    )
    async def completions(self, request: RequestType) -> RESTResponse:
        """
        Return auto-completion suggestions for a given query.
        """
        args = request.query
        if "q" not in args:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "query parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        keywords = args["q"].strip().lower()
        results = request.context[0].get_auto_complete_terms(keywords, max_terms=5)
        return RESTResponse({"completions": results})
