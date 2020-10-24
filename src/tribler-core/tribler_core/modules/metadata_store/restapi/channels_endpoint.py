import base64
import codecs
from binascii import unhexlify

from aiohttp import ClientSession, ContentTypeError, web

from aiohttp_apispec import docs, json_schema

from ipv8.REST.schema import schema
from ipv8.database import database_blob

from marshmallow.fields import Boolean, Dict, Integer, String

from pony.orm import db_session

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.orm_bindings.channel_node import DIRTY_STATUSES, NEW
from tribler_core.modules.metadata_store.restapi.metadata_endpoint_base import MetadataEndpointBase
from tribler_core.modules.metadata_store.restapi.metadata_schema import ChannelSchema
from tribler_core.modules.metadata_store.serialization import REGULAR_TORRENT
from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTResponse
from tribler_core.restapi.schema import HandledErrorSchema
from tribler_core.utilities import path_util
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import is_infohash, parse_magnetlink


class ChannelsEndpointBase(MetadataEndpointBase):
    pass


class ChannelsEndpoint(ChannelsEndpointBase):
    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('', self.get_channels),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}', self.get_channel_contents),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/copy', self.copy_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/channels', self.create_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/collections', self.create_collection),
                web.put(r'/{channel_pk:\w*}/{channel_id:\w*}/torrents', self.add_torrent_to_channel),
                web.post(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.post_commit),
                web.get(r'/{channel_pk:\w*}/{channel_id:\w*}/commit', self.is_channel_dirty),
            ]
        )

    def get_channel_from_request(self, request):
        channel_pk = (
            self.session.mds.my_key.pub().key_to_bin()[10:]
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
    # TODO: DRY it with SpecificChannel endpoint?
    async def get_channels(self, request):
        sanitized = self.sanitize_parameters(request.query)
        sanitized['subscribed'] = None if 'subscribed' not in request.query else bool(int(request.query['subscribed']))
        include_total = request.query.get('include_total', '')
        sanitized.update({"origin_id": 0})

        with db_session:
            channels = self.session.mds.ChannelMetadata.get_entries(**sanitized)
            total = self.session.mds.ChannelMetadata.get_total_count(**sanitized) if include_total else None
            channels_list = []
            for channel in channels:
                channel_dict = channel.to_simple_dict()
                # Add progress info for those channels that are still being processed
                if channel.subscribed:
                    if channel_dict["state"] == CHANNEL_STATE.UPDATING.value:
                        try:
                            progress = self.session.mds.compute_channel_update_progress(channel)
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
                        if not self.session.dlmgr.metainfo_requests.get(
                            bytes(channel.infohash)
                        ) and self.session.dlmgr.download_exists(bytes(channel.infohash)):
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
                        'results': [Dict()],
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
        sanitized = self.sanitize_parameters(request.query)
        include_total = request.query.get('include_total', '')
        channel_pk, channel_id = self.get_channel_from_request(request)
        sanitized.update({"channel_pk": channel_pk, "origin_id": channel_id})
        with db_session:
            contents = self.session.mds.MetadataNode.get_entries(**sanitized)
            contents_list = [c.to_simple_dict() for c in contents]
            total = self.session.mds.MetadataNode.get_total_count(**sanitized) if include_total else None
        for torrent in contents_list:
            if torrent['type'] == REGULAR_TORRENT:
                dl = self.session.dlmgr.get_download(unhexlify(torrent['infohash']))
                if dl is not None:
                    torrent['progress'] = dl.get_state().get_progress()
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
            personal_root = channel_id == 0 and channel_pk == self.session.mds.my_key.pub().key_to_bin()[10:]
            # TODO: better error handling
            target_collection = self.session.mds.CollectionNode.get(
                public_key=database_blob(channel_pk), id_=channel_id
            )
            try:
                request_parsed = await request.json()
            except (ContentTypeError, ValueError):
                return RESTResponse({"error": "Bad JSON"}, status=HTTP_BAD_REQUEST)

            if not target_collection and not personal_root:
                return RESTResponse({"error": "Target channel not found"}, status=HTTP_NOT_FOUND)
            results_list = []
            for entry in request_parsed:
                public_key, id_ = database_blob(unhexlify(entry["public_key"])), entry["id"]
                source = self.session.mds.ChannelNode.get(public_key=public_key, id_=id_)
                if not source:
                    return RESTResponse({"error": "Source entry not found"}, status=HTTP_BAD_REQUEST)
                # We must upgrade Collections to Channels when moving them to root channel, and, vice-versa,
                # downgrade Channels to Collections when moving them into existing channels
                if isinstance(source, self.session.mds.CollectionNode):
                    src_dict = source.to_dict()
                    if channel_id == 0:
                        rslt = self.session.mds.ChannelMetadata.create_channel(title=source.title)
                    else:
                        dst_dict = {'origin_id': channel_id, "status": NEW}
                        for k in self.session.mds.CollectionNode.nonpersonal_attributes:
                            dst_dict[k] = src_dict[k]
                        dst_dict.pop("metadata_type")
                        rslt = self.session.mds.CollectionNode(**dst_dict)
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
                'schema': schema(CreateChannelResponse={'results': [Dict()]}),
            }
        },
    )
    async def create_channel(self, request):
        with db_session:
            _, channel_id = self.get_channel_from_request(request)
            request_parsed = await request.json()
            channel_name = request_parsed.get("name", "New channel")
            md = self.session.mds.ChannelMetadata.create_channel(channel_name, origin_id=channel_id)
            return RESTResponse({"results": [md.to_simple_dict()]})

    @docs(
        tags=['Metadata'],
        summary='Create a new collection entry in the given channel.',
        responses={
            200: {
                'description': 'Returns the newly created collection',
                'schema': schema(CreateCollectionResponse={'results': [Dict()]}),
            }
        },
    )
    async def create_collection(self, request):
        with db_session:
            _, channel_id = self.get_channel_from_request(request)
            request_parsed = await request.json()
            collection_name = request_parsed.get("name", "New collection")
            md = self.session.mds.CollectionNode(origin_id=channel_id, title=collection_name, status=NEW)
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
            channel = self.session.mds.CollectionNode.get(public_key=database_blob(channel_pk), id_=channel_id)
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
                async with ClientSession() as session:
                    response = await session.get(uri)
                    data = await response.read()
                tdef = TorrentDef.load_from_memory(data)
            elif uri.startswith("magnet:"):
                _, xt, _ = parse_magnetlink(uri)
                if (
                    xt
                    and is_infohash(codecs.encode(xt, 'hex'))
                    and (
                        self.session.mds.torrent_exists_in_personal_channel(xt)
                        or channel.copy_torrent_from_infohash(xt)
                    )
                ):
                    return RESTResponse({"added": 1})

                meta_info = await self.session.dlmgr.get_metainfo(xt, timeout=30, url=uri)
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
            if not path_util.isabs(torrents_dir):
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
            torrents_list, errors_list = channel.add_torrents_from_dir(torrents_dir, recursive)
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
                for t in self.session.mds.CollectionNode.commit_all_channels():
                    self.session.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(t))
            else:
                coll = self.session.mds.CollectionNode.get(public_key=database_blob(channel_pk), id_=channel_id)
                if not coll:
                    return RESTResponse({"success": False}, status=HTTP_NOT_FOUND)
                torrent_dict = coll.commit_channel_torrent()
                if torrent_dict:
                    self.session.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(torrent_dict))

        return RESTResponse({"success": True})

    @docs(
        tags=['Metadata'],
        summary='Check if a channel has uncommitted changes.',
        responses={200: {'schema': schema(IsChannelDirtyResponse={'dirty': Boolean()})}},
    )
    async def is_channel_dirty(self, request):
        channel_pk, _ = self.get_channel_from_request(request)
        with db_session:
            dirty = self.session.mds.MetadataNode.exists(
                lambda g: g.public_key == database_blob(channel_pk) and g.status in DIRTY_STATUSES
            )
            return RESTResponse({"dirty": dirty})
