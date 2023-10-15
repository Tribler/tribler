from binascii import unhexlify
from typing import Optional

from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.base_endpoint import HTTP_BAD_REQUEST
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Integer
from pony.orm import db_session

from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.restapi.metadata_endpoint_base import MetadataEndpointBase
from tribler.core.components.metadata_store.restapi.metadata_schema import TorrentSchema
from tribler.core.components.restapi.rest.rest_endpoint import RESTResponse
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.utilities.utilities import froze_it

TORRENT_CHECK_TIMEOUT = 20


@froze_it
class MetadataEndpoint(MetadataEndpointBase):
    """
    This is the top-level endpoint class that serves other endpoints.

    # /metadata
    #          /torrents
    #          /<public_key>
    """
    path = '/metadata'

    def __init__(self, download_manager: DownloadManager,
                 torrent_checker: Optional[TorrentChecker], *args, **kwargs):
        MetadataEndpointBase.__init__(self, *args, **kwargs)
        self.download_manager = download_manager
        self.torrent_checker = torrent_checker

    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/torrents/{infohash}/health', self.get_torrent_health),
                web.get('/torrents/popular', self.get_popular_torrents),
            ]
        )

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

        if self.tag_rules_processor:
            await self.tag_rules_processor.process_queue()

        self.add_download_progress_to_metadata_list(contents_list)
        self.add_statements_to_metadata_list(contents_list, hide_xxx=sanitized["hide_xxx"])
        response_dict = {
            "results": contents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
        }

        return RESTResponse(response_dict)
