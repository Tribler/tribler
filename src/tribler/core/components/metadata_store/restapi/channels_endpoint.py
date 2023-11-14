import base64
import json
from asyncio import CancelledError
from binascii import unhexlify
from pathlib import Path

from aiohttp import ClientSession, ContentTypeError, web
from aiohttp_apispec import docs, json_schema, querystring_schema
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, Integer, String
from pony.orm import db_session

from tribler.core.components.gigachannel.community.gigachannel_community import GigaChannelCommunity
from tribler.core.components.gigachannel_manager.gigachannel_manager import GigaChannelManager
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.torrentdef import TorrentDef
from tribler.core.components.metadata_store.db.orm_bindings.channel_node import DIRTY_STATUSES, NEW
from tribler.core.components.metadata_store.db.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler.core.components.metadata_store.restapi.metadata_endpoint_base import MetadataEndpointBase
from tribler.core.components.metadata_store.restapi.metadata_schema import ChannelSchema, MetadataParameters, MetadataSchema, TorrentSchema
from tribler.core.components.metadata_store.utils import NoChannelSourcesException, RequestTimeoutException
from tribler.core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTResponse
from tribler.core.components.restapi.rest.schema import HandledErrorSchema
from tribler.core.utilities.simpledefs import CHANNEL_STATE
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import froze_it, parse_bool, parse_magnetlink

ERROR_INVALID_MAGNET_LINK = "Invalid magnet link: %s"


async def _fetch_uri(uri):
    async with ClientSession() as session:
        response = await session.get(uri)
        data = await response.read()
    return data


@froze_it
class ChannelsEndpoint(MetadataEndpointBase):
    path = '/channels'

    def __init__(self,
                 download_manager: DownloadManager,
                 gigachannel_manager: GigaChannelManager,
                 gigachannel_community: GigaChannelCommunity,
                 *args, **kwargs):
        MetadataEndpointBase.__init__(self, *args, **kwargs)
        self.download_manager = download_manager
        self.gigachannel_manager = gigachannel_manager
        self.gigachannel_community = gigachannel_community

    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('', self.get_channels),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}', self.get_channel_contents),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}/description', self.get_channel_description),
                web.put(r'/{channel_pk:\w*}/{channel_id:\w*}/description', self.put_channel_description),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}/thumbnail', self.get_channel_thumbnail),
                web.put(r'/{channel_pk:\w*}/{channel_id:\w*}/thumbnail', self.put_channel_thumbnail),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/copy', self.copy_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/channels', self.create_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/collections', self.create_collection),
                web.put(r'/{channel_pk:\w*}/{channel_id:\w*}/torrents', self.add_torrent_to_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.post_commit),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.is_channel_dirty),
                web.get('/popular_torrents', self.get_popular_torrents_channel),
            ]
        )

    def add_download_progress_to_metadata_list(self, contents_list):
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                dl = self.download_manager.get_download(unhexlify(torrent['infohash']))
                if dl is not None and dl.tdef.infohash not in self.download_manager.metainfo_requests:
                    torrent['progress'] = dl.get_state().get_progress()

    def get_channel_from_request(self, request):
        channel_pk = (
            self.mds.my_key.pub().key_to_bin()[10:]
            if request.match_info['channel_pk'] == 'mychannel'
            else unhexlify(request.match_info['channel_pk'])
        )
        channel_id = int(request.match_info['channel_id'])
        return channel_pk, channel_id

    @docs(
        tags=['Metadata'],
        summary='Get a list of all channels known to the system.',
        responses={
            200: {
                'schema': schema(
                    GetChannelsResponse={
                        'results': [ChannelSchema],
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
    @querystring_schema(MetadataParameters)
    async def get_channels(self, request):
        sanitized = self.sanitize_parameters(request.query)
        sanitized['subscribed'] = None if 'subscribed' not in request.query else parse_bool(request.query['subscribed'])
        include_total = request.query.get('include_total', '')
        sanitized.update({"origin_id": 0})
        sanitized['metadata_type'] = CHANNEL_TORRENT

        with db_session:
            channels = self.mds.get_entries(**sanitized)
            total = self.mds.get_total_count(**sanitized) if include_total else None
            channels_list = []
            for channel in channels:
                channel_dict = channel.to_simple_dict()
                # Add progress info for those channels that are still being processed
                if channel.subscribed:
                    if channel_dict["state"] == CHANNEL_STATE.UPDATING.value:
                        try:
                            progress = self.mds.compute_channel_update_progress(channel)
                            channel_dict["progress"] = progress
                        except (ZeroDivisionError, FileNotFoundError) as e:
                            self._logger.error(
                                "Error %s when calculating channel update progress. Channel data: %s-%i %i/%i",
                                e,
                                hexlify(channel.public_key),
                                channel.id_,
                                channel.start_timestamp,
                                channel.local_version,
                            )
                    elif channel_dict["state"] == CHANNEL_STATE.METAINFO_LOOKUP.value:
                        if not self.download_manager.metainfo_requests.get(
                                bytes(channel.infohash)
                        ) and self.download_manager.download_exists(bytes(channel.infohash)):
                            channel_dict["state"] = CHANNEL_STATE.DOWNLOADING.value

                channels_list.append(channel_dict)
        response_dict = {
            "results": channels_list,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": int(sanitized["sort_desc"]),
        }
        if total is not None:
            response_dict.update({"total": total})
        return RESTResponse(response_dict)

    @docs(
        tags=['Metadata'],
        summary='Get a list of the channel\'s contents (torrents/channels/etc.).',
        responses={
            200: {
                'schema': schema(
                    GetChannelContentsResponse={
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
    async def get_channel_contents(self, request):
        self._logger.info('Get channel content')
        sanitized = self.sanitize_parameters(request.query)
        include_total = request.query.get('include_total', '')
        channel_pk, channel_id = self.get_channel_from_request(request)
        sanitized.update({"channel_pk": channel_pk, "origin_id": channel_id})
        remote = sanitized.pop("remote", None)

        total = None

        remote_failed = False
        if remote:
            try:
                self._logger.info('Receive remote content')
                contents_list = await self.gigachannel_community.remote_select_channel_contents(**sanitized)
            except (RequestTimeoutException, NoChannelSourcesException, CancelledError):
                remote_failed = True
                self._logger.info('Remote request failed')

        if not remote or remote_failed:
            self._logger.info('Receive local content')
            with db_session:
                contents = self.mds.get_entries(**sanitized)
                contents_list = []
                for entry in contents:
                    contents_list.append(entry.to_simple_dict())
                total = self.mds.get_total_count(**sanitized) if include_total else None

        if self.tag_rules_processor:
            await self.tag_rules_processor.process_queue()

        self.add_download_progress_to_metadata_list(contents_list)
        self.add_statements_to_metadata_list(contents_list, hide_xxx=sanitized["hide_xxx"])
        response_dict = {
            "results": contents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
            "sort_by": sanitized['sort_by'],
            "sort_desc": int(sanitized['sort_desc']),
        }
        if total is not None:
            response_dict.update({"total": total})

        return RESTResponse(response_dict)

    async def get_channel_description(self, request):
        channel_pk, channel_id = self.get_channel_from_request(request)
        with db_session:
            channel_description = self.mds.ChannelDescription.select(
                lambda g: g.public_key == channel_pk and g.origin_id == channel_id
            ).first()

        response_dict = json.loads(channel_description.json_text) if (channel_description is not None) else {}
        return RESTResponse(response_dict)

    async def put_channel_description(self, request):
        channel_pk, channel_id = self.get_channel_from_request(request)
        request_parsed = await request.json()
        updated_json_text = json.dumps({"description_text": request_parsed["description_text"]})
        with db_session:
            channel_description = self.mds.ChannelDescription.select(
                lambda g: g.public_key == channel_pk and g.origin_id == channel_id
            ).first()
            if channel_description is not None:
                channel_description.update_properties({"json_text": updated_json_text})
            else:
                channel_description = self.mds.ChannelDescription(
                    public_key=channel_pk, origin_id=channel_id, json_text=updated_json_text, status=NEW
                )
        return RESTResponse(json.loads(channel_description.json_text))

    async def get_channel_thumbnail(self, request):
        channel_pk, channel_id = self.get_channel_from_request(request)
        with db_session:
            obj = self.mds.ChannelThumbnail.select(
                lambda g: g.public_key == channel_pk and g.origin_id == channel_id
            ).first()
        return web.Response(body=obj.binary_data, content_type=obj.data_type) if obj else web.Response(status=400)

    async def put_channel_thumbnail(self, request):
        content_type = request.headers["Content-Type"]
        post_body = await request.read()
        channel_pk, channel_id = self.get_channel_from_request(request)
        obj_properties = {"binary_data": post_body, "data_type": content_type}
        with db_session:
            obj = self.mds.ChannelThumbnail.select(
                lambda g: g.public_key == channel_pk and g.origin_id == channel_id,
            ).first()
            if obj is not None:
                obj.update_properties(obj_properties)
            else:
                self.mds.ChannelThumbnail(public_key=channel_pk, origin_id=channel_id, status=NEW, **obj_properties)
        return web.Response(status=201)

    @docs(
        tags=['Metadata'],
        summary='Create a copy of an entry/entries from another channel.',
        parameters=[
            {
                'in': 'body',
                'name': 'entries',
                'description': 'List of entries to copy',
                'example': [{'public_key': '1234567890', 'id': 123}],
                'required': True,
            }
        ],
        responses={
            200: {'description': 'Returns a list of copied content'},
            HTTP_NOT_FOUND: {'schema': HandledErrorSchema, 'example': {"error": "Target channel not found"}},
            HTTP_BAD_REQUEST: {'schema': HandledErrorSchema, 'example': {"error": "Source entry not found"}},
        },
    )
    async def copy_channel(self, request):
        with db_session:
            channel_pk, channel_id = self.get_channel_from_request(request)
            personal_root = channel_id == 0 and channel_pk == self.mds.my_key.pub().key_to_bin()[10:]
            # TODO: better error handling
            target_collection = self.mds.CollectionNode.get(public_key=channel_pk, id_=channel_id)
            try:
                request_parsed = await request.json()
            except (ContentTypeError, ValueError):
                return RESTResponse({"error": "Bad JSON"}, status=HTTP_BAD_REQUEST)

            if not target_collection and not personal_root:
                return RESTResponse({"error": "Target channel not found"}, status=HTTP_NOT_FOUND)
            results_list = []
            for entry in request_parsed:
                public_key, id_ = unhexlify(entry["public_key"]), entry["id"]
                source = self.mds.ChannelNode.get(public_key=public_key, id_=id_)
                if not source:
                    return RESTResponse({"error": "Source entry not found"}, status=HTTP_BAD_REQUEST)
                # We must upgrade Collections to Channels when moving them to root channel, and, vice-versa,
                # downgrade Channels to Collections when moving them into existing channels
                if isinstance(source, self.mds.CollectionNode):
                    src_dict = source.to_dict()
                    if channel_id == 0:
                        rslt = self.mds.ChannelMetadata.create_channel(title=source.title)
                    else:
                        dst_dict = {'origin_id': channel_id, "status": NEW}
                        for k in self.mds.CollectionNode.nonpersonal_attributes:
                            dst_dict[k] = src_dict[k]
                        dst_dict.pop("metadata_type")
                        rslt = self.mds.CollectionNode(**dst_dict)
                    for child in source.actual_contents:
                        child.make_copy(rslt.id_)
                else:
                    rslt = source.make_copy(channel_id)
                results_list.append(rslt.to_simple_dict())
            return RESTResponse(results_list)

    @docs(
        tags=['Metadata'],
        summary='Create a new channel entry in the given channel.',
        responses={
            200: {
                'description': 'Returns the newly created channel',
                'schema': schema(CreateChannelResponse={'results': [ChannelSchema]}),
            }
        },
    )
    async def create_channel(self, request):
        with db_session:
            _, channel_id = self.get_channel_from_request(request)
            request_parsed = await request.json()
            channel_name = request_parsed.get("name", "New channel")
            md = self.mds.ChannelMetadata.create_channel(channel_name, origin_id=channel_id)
            return RESTResponse({"results": [md.to_simple_dict()]})

    @docs(
        tags=['Metadata'],
        summary='Create a new collection entry in the given channel.',
        responses={
            200: {
                'description': 'Returns the newly created collection',
                'schema': schema(CreateCollectionResponse={'results': [ChannelSchema]}),
            }
        },
    )
    async def create_collection(self, request):
        with db_session:
            _, channel_id = self.get_channel_from_request(request)
            request_parsed = await request.json()
            collection_name = request_parsed.get("name", "New collection")
            md = self.mds.CollectionNode(origin_id=channel_id, title=collection_name, status=NEW)
            return RESTResponse({"results": [md.to_simple_dict()]})

    @docs(
        tags=['Metadata'],
        summary='Add a torrent file to your own channel.',
        responses={
            200: {
                'schema': schema(
                    AddTorrentToChannelResponse={'added': (Integer, 'Number of torrent that were added to the channel')}
                )
            },
            HTTP_NOT_FOUND: {'schema': HandledErrorSchema, 'example': {"error": "Unknown channel"}},
            HTTP_BAD_REQUEST: {'schema': HandledErrorSchema, 'example': {"error": "unknown uri type"}},
        },
    )
    @json_schema(
        schema(
            AddTorrentToChannelRequest={
                'torrent': (String, 'Base64-encoded torrent file'),
                'uri': (String, 'Add a torrent from a magnet link or URL'),
                'torrents_dir': (String, 'Add all .torrent files from a chosen directory'),
                'recursive': (Boolean, 'Toggle recursive scanning of the chosen directory for .torrent files'),
                'description': (String, 'Description for the torrent'),
            }
        )
    )
    async def add_torrent_to_channel(self, request):
        channel_pk, channel_id = self.get_channel_from_request(request)
        with db_session:
            channel = self.mds.CollectionNode.get(public_key=channel_pk, id_=channel_id)
        if not channel:
            return RESTResponse({"error": "Unknown channel"}, status=HTTP_NOT_FOUND)

        parameters = await request.json()

        extra_info = {}
        if parameters.get('description', None):
            extra_info = {'description': parameters['description']}

        # First, check whether we did upload a magnet link or URL
        if parameters.get('uri', None):
            uri = parameters['uri']
            if uri.startswith("http:") or uri.startswith("https:"):
                data = await _fetch_uri(uri)
                tdef = TorrentDef.load_from_memory(data)
            elif uri.startswith("magnet:"):
                _, xt, _ = parse_magnetlink(uri)

                if not xt:
                    return RESTResponse({"error": ERROR_INVALID_MAGNET_LINK.format(uri)}, status=HTTP_BAD_REQUEST)

                if self.mds.torrent_exists_in_personal_channel(xt) or channel.copy_torrent_from_infohash(xt):
                    return RESTResponse({"added": 1})

                meta_info = await self.download_manager.get_metainfo(xt, timeout=30, url=uri)
                if not meta_info:
                    raise RuntimeError("Metainfo timeout")
                tdef = TorrentDef.load_from_dict(meta_info)
            else:
                return RESTResponse({"error": "unknown uri type"}, status=HTTP_BAD_REQUEST)

            added = 0
            if tdef:
                channel.add_torrent_to_channel(tdef, extra_info)
                added = 1
            return RESTResponse({"added": added})

        torrents_dir = None
        if parameters.get('torrents_dir', None):
            torrents_dir = parameters['torrents_dir']
            if not Path(torrents_dir).is_absolute():
                return RESTResponse({"error": "the torrents_dir should point to a directory"}, status=HTTP_BAD_REQUEST)

        recursive = False
        if parameters.get('recursive'):
            recursive = parameters['recursive']
            if not torrents_dir:
                return RESTResponse(
                    {"error": "the torrents_dir parameter should be provided when the recursive parameter is set"},
                    status=HTTP_BAD_REQUEST,
                )

        if torrents_dir:
            torrents_list, errors_list = await channel.add_torrents_from_dir(torrents_dir, recursive)
            return RESTResponse({"added": len(torrents_list), "errors": errors_list})

        if not parameters.get('torrent', None):
            return RESTResponse({"error": "torrent parameter missing"}, status=HTTP_BAD_REQUEST)

        # Try to parse the torrent data
        # Any errors will be handled by the error_middleware
        torrent = base64.b64decode(parameters['torrent'])
        torrent_def = TorrentDef.load_from_memory(torrent)
        channel.add_torrent_to_channel(torrent_def, extra_info)
        return RESTResponse({"added": 1})

    @docs(
        tags=['Metadata'],
        summary='Commit a channel.',
        responses={200: {'schema': schema(CommitResponse={'success': Boolean()})}},
    )
    async def post_commit(self, request):
        channel_pk, channel_id = self.get_channel_from_request(request)
        with db_session:
            if channel_id == 0:
                for t in self.mds.CollectionNode.commit_all_channels():
                    self.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(t))
            else:
                coll = self.mds.CollectionNode.get(public_key=channel_pk, id_=channel_id)
                if not coll:
                    return RESTResponse({"success": False}, status=HTTP_NOT_FOUND)
                torrent_dict = coll.commit_channel_torrent()
                if torrent_dict:
                    self.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(torrent_dict))

        return RESTResponse({"success": True})

    @docs(
        tags=['Metadata'],
        summary='Check if a channel has uncommitted changes.',
        responses={200: {'schema': schema(IsChannelDirtyResponse={'dirty': Boolean()})}},
    )
    async def is_channel_dirty(self, request):
        channel_pk, _ = self.get_channel_from_request(request)
        with db_session:
            dirty = self.mds.MetadataNode.exists(lambda g: g.public_key == channel_pk and g.status in DIRTY_STATUSES)
            return RESTResponse({"dirty": dirty})

    @docs(
        tags=['Metadata'],
        summary='Get the list of most popular torrents. Functions as a pseudo-channel.',
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
    async def get_popular_torrents_channel(self, request):
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
