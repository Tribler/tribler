import time
import typing
from binascii import unhexlify
from dataclasses import asdict

from aiohttp import web
from aiohttp_apispec import docs, querystring_schema
from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Integer, String
from pony.orm import db_session

from tribler.core.components.database.category_filter.family_filter import default_xxx_filter
from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.database.db.serialization import REGULAR_TORRENT
from tribler.core.components.database.db.store import MetadataStore
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.database.restapi.schema import MetadataSchema, SearchMetadataParameters, TorrentSchema
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.restapi.rest.rest_endpoint import MAX_REQUEST_SIZE, RESTEndpoint, RESTResponse
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.utilities import froze_it, parse_bool

TORRENT_CHECK_TIMEOUT = 20
SNIPPETS_TO_SHOW = 3  # The number of snippets we return from the search results
MAX_TORRENTS_IN_SNIPPETS = 4  # The maximum number of torrents in each snippet

# This dict is used to translate JSON fields into the columns used in Pony for _sorting_.
# id_ is not in the list because there is not index on it, so we never really want to sort on it.
json2pony_columns = {
    'category': "tags",
    'name': "title",
    'size': "size",
    'infohash': "infohash",
    'date': "torrent_date",
    'created': "torrent_date",
    'status': 'status',
    'votes': 'votes',
    'subscribed': 'subscribed',
    'health': 'HEALTH',
}


@froze_it
class DatabaseEndpoint(RESTEndpoint):
    """
    This is the top-level endpoint class that serves other endpoints.

    # /metadata
    #          /torrents
    #          /<public_key>
    """
    path = '/metadata'

    def __init__(self,
                 download_manager: DownloadManager,
                 torrent_checker: typing.Optional[TorrentChecker],
                 metadata_store: MetadataStore,
                 tribler_db: TriblerDatabase = None,
                 middlewares=(),
                 client_max_size=MAX_REQUEST_SIZE):
        super().__init__(middlewares, client_max_size)
        self.download_manager = download_manager
        self.torrent_checker = torrent_checker
        self.mds = metadata_store
        self.tribler_db: typing.Optional[TriblerDatabase] = tribler_db

    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/torrents/{infohash}/health', self.get_torrent_health),
                web.get('/torrents/popular', self.get_popular_torrents),
                web.get('/search/local', self.local_search),
                web.get('/search/completions', self.completions)
            ]
        )

    @classmethod
    def sanitize_parameters(cls, parameters):
        """
        Sanitize the parameters for a request that fetches channels.
        """
        sanitized = {
            "first": int(parameters.get('first', 1)),
            "last": int(parameters.get('last', 50)),
            "sort_by": json2pony_columns.get(parameters.get('sort_by')),
            "sort_desc": parse_bool(parameters.get('sort_desc', True)),
            "txt_filter": parameters.get('txt_filter'),
            "hide_xxx": parse_bool(parameters.get('hide_xxx', False)),
            "category": parameters.get('category'),
        }
        if 'tags' in parameters:
            sanitized['tags'] = parameters.getall('tags')
        if "max_rowid" in parameters:
            sanitized["max_rowid"] = int(parameters["max_rowid"])
        if "channel_pk" in parameters:
            sanitized["channel_pk"] = unhexlify(parameters["channel_pk"])
        if "origin_id" in parameters:
            sanitized["origin_id"] = int(parameters["origin_id"])
        return sanitized

    @db_session
    def add_statements_to_metadata_list(self, contents_list, hide_xxx=False):
        if self.tribler_db is None:
            self._logger.error(f'Cannot add statements to metadata list: '
                               f'tribler_db is not set in {self.__class__.__name__}')
            return
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                raw_statements = self.tribler_db.knowledge.get_statements(
                    subject_type=ResourceType.TORRENT,
                    subject=torrent["infohash"]
                )
                statements = [asdict(stmt) for stmt in raw_statements]
                if hide_xxx:
                    statements = [stmt for stmt in statements if not default_xxx_filter.isXXX(stmt["object"],
                                                                                              isFilename=False)]
                torrent["statements"] = statements

    @docs(
        tags=["Metadata"],
        summary="Fetch the swarm health of a specific torrent.",
        parameters=[
            {
                'in': 'path',
                'name': 'infohash',
                'description': 'Infohash of the download to remove',
                'type': 'string',
                'required': True,
            },
            {
                'in': 'query',
                'name': 'timeout',
                'description': 'Timeout to be used in the connections to the trackers',
                'type': 'integer',
                'default': 20,
                'required': False,
            },
        ],
        responses={
            200: {
                'schema': schema(
                    HealthCheckResponse={
                        'checking': Boolean()
                    }
                ),
                'examples': [
                    {'checking': 1},
                ],
            }
        },
    )
    async def get_torrent_health(self, request):
        self._logger.info(f'Get torrent health request: {request}')
        try:
            timeout = int(request.query.get('timeout', TORRENT_CHECK_TIMEOUT))
        except ValueError as e:
            return RESTResponse({"error": f"Error processing timeout parameter: {e}"}, status=HTTP_BAD_REQUEST)

        if self.torrent_checker is None:
            return RESTResponse({'checking': False})

        infohash = unhexlify(request.match_info['infohash'])
        check_coro = self.torrent_checker.check_torrent_health(infohash, timeout=timeout, scrape_now=True)
        self.async_group.add_task(check_coro)
        return RESTResponse({'checking': True})

    def add_download_progress_to_metadata_list(self, contents_list):
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                dl = self.download_manager.get_download(unhexlify(torrent['infohash']))
                if dl is not None and dl.tdef.infohash not in self.download_manager.metainfo_requests:
                    torrent['progress'] = dl.get_state().get_progress()

    @docs(
        tags=['Metadata'],
        summary='Get the list of most popular torrents.',
        responses={
            200: {
                'schema': schema(
                    GetPopularTorrentsResponse={
                        'results': [TorrentSchema],
                        'first': Integer(),
                        'last': Integer(),
                    }
                )
            }
        },
    )
    async def get_popular_torrents(self, request):
        sanitized = self.sanitize_parameters(request.query)
        sanitized["metadata_type"] = REGULAR_TORRENT
        sanitized["popular"] = True

        with db_session:
            contents = self.mds.get_entries(**sanitized)
            contents_list = []
            for entry in contents:
                contents_list.append(entry.to_simple_dict())

        self.add_download_progress_to_metadata_list(contents_list)
        self.add_statements_to_metadata_list(contents_list, hide_xxx=sanitized["hide_xxx"])
        response_dict = {
            "results": contents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
        }

        return RESTResponse(response_dict)

    @docs(
        tags=['Metadata'],
        summary="Perform a search for a given query.",
        responses={
            200: {
                'schema': schema(
                    SearchResponse={
                        'results': [MetadataSchema],
                        'first': Integer(),
                        'last': Integer(),
                        'sort_by': String(),
                        'sort_desc': Integer(),
                        'total': Integer(),
                    }
                )
            }
        },
    )
    @querystring_schema(SearchMetadataParameters)
    async def local_search(self, request):
        try:
            sanitized = self.sanitize_parameters(request.query)
            tags = sanitized.pop('tags', None)
        except (ValueError, KeyError):
            return RESTResponse({"error": "Error processing request parameters"}, status=HTTP_BAD_REQUEST)

        include_total = request.query.get('include_total', '')

        mds: MetadataStore = self.mds

        def search_db():
            with db_session:
                t1 = time.time()
                pony_query = mds.get_entries(**sanitized)
                t2 = time.time()
                search_results = [r.to_simple_dict() for r in pony_query]
                t3 = time.time()
                if include_total:
                    total = mds.get_total_count(**sanitized)
                    t4 = time.time()
                    max_rowid = mds.get_max_rowid()
                    t5 = time.time()
                    self._logger.info(f'Search performance for {sanitized}:\n'
                                      f'Main query executed in {t2 - t1:.6} seconds;\n'
                                      f'Result constructed in {t3 - t2:.6} seconds;\n'
                                      f'Total rows count calculated in {t4 - t3:.6} seconds;\n'
                                      f'Max rowid determined in {t5 - t4:.6} seconds.')
                else:
                    total = max_rowid = None
                    self._logger.info(f'Search performance for {sanitized}:\n'
                                      f'Main query executed in {t2 - t1:.6} seconds;\n'
                                      f'Result constructed in {t3 - t2:.6} seconds.')

            return search_results, total, max_rowid

        try:
            with db_session:
                if tags:
                    infohash_set = self.tribler_db.knowledge.get_subjects_intersection(
                        subjects_type=ResourceType.TORRENT,
                        objects=set(tags),
                        predicate=ResourceType.TAG,
                        case_sensitive=False)
                    if infohash_set:
                        sanitized['infohash_set'] = {bytes.fromhex(s) for s in infohash_set}

            search_results, total, max_rowid = await run_threaded(mds.db, search_db)
        except Exception as e:  # pylint: disable=broad-except;  # pragma: no cover
            self._logger.exception("Error while performing DB search: %s: %s", type(e).__name__, e)
            return RESTResponse(status=HTTP_BAD_REQUEST)

        self.add_statements_to_metadata_list(search_results, hide_xxx=sanitized["hide_xxx"])

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
        tags=['Metadata'],
        summary="Return auto-completion suggestions for a given query.",
        parameters=[{'in': 'query', 'name': 'q', 'description': 'Search query', 'type': 'string', 'required': True}],
        responses={
            200: {
                'schema': schema(
                    CompletionsResponse={
                        'completions': [String],
                    }
                ),
                'examples': {'completions': ['pioneer one', 'pioneer movie']},
            }
        },
    )
    async def completions(self, request):
        args = request.query
        if 'q' not in args:
            return RESTResponse({"error": "query parameter missing"}, status=HTTP_BAD_REQUEST)

        keywords = args['q'].strip().lower()
        # TODO: add XXX filtering for completion terms
        results = self.mds.get_auto_complete_terms(keywords, max_terms=5)
        return RESTResponse({"completions": results})
