from __future__ import absolute_import

import base64
import codecs
import logging
import os
from binascii import unhexlify

from ipv8.database import database_blob

from pony.orm import db_session

from twisted.internet.defer import Deferred
from twisted.internet.error import ConnectionDone
from twisted.web import http
from twisted.web.error import SchemeNotSupported
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import DIRTY_STATUSES, NEW
from Tribler.Core.Modules.restapi.metadata_endpoint_base import MetadataEndpointBase
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import recursive_unicode
from Tribler.Core.Utilities.utilities import http_get, is_infohash, parse_magnetlink
from Tribler.Core.exceptions import DuplicateTorrentFileError


class ChannelsEndpointBase(MetadataEndpointBase):
    pass


class ChannelsEndpoint(ChannelsEndpointBase):
    """
    The channels endpoint.

    # /channels
    #                   /popular
    #                   /<public_key>
    """

    def getChild(self, path, request):
        if path == b"popular":
            return ChannelsPopularEndpoint(self.session)
        return ChannelsPublicKeyEndpoint(self.session, path)

    @classmethod
    def sanitize_parameters(cls, parameters):
        return dict(
            subscribed=None if 'subscribed' not in parameters else bool(int(parameters['subscribed'][0]) > 0),
            **ChannelsEndpointBase.sanitize_parameters(parameters)
        )

    # Get list of all channels known to the system
    # TODO: DRY it with SpecificChannel endpoint?
    def render_GET(self, request):
        args = recursive_unicode(request.args)
        sanitized = self.sanitize_parameters(args)
        include_total = args['include_total'][0] if 'include_total' in args else ''
        sanitized.update({"origin_id": 0})

        with db_session:
            channels = self.session.lm.mds.ChannelMetadata.get_entries(**sanitized)
            total = self.session.lm.mds.ChannelMetadata.get_total_count(**sanitized) if include_total else None
            channels_list = [channel.to_simple_dict() for channel in channels]
        response_dict = {
            "results": channels_list,
            "first": sanitized["first"],
            "last": sanitized["last"],
            "sort_by": sanitized["sort_by"],
            "sort_desc": int(sanitized["sort_desc"]),
        }
        if total is not None:
            response_dict.update({"total": total})
        return json.twisted_dumps(response_dict)


class ChannelsPopularEndpoint(ChannelsEndpointBase):
    """
    The endpoint to serve the most popular channels

    # /popular
    """

    def render_GET(self, request):
        limit_channels = 10
        args = recursive_unicode(request.args)

        if 'limit' in args and args['limit']:
            limit_channels = int(args['limit'][0])

            if limit_channels <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "the limit parameter must be a positive number"})

        with db_session:
            popular_channels = self.session.lm.mds.ChannelMetadata.get_random_channels(limit=limit_channels)
            results = [channel.to_simple_dict() for channel in popular_channels]
        return json.twisted_dumps({"channels": results})


class ChannelsPublicKeyEndpoint(ChannelsEndpointBase):
    """
    An intermediate endpoint parsing the public_key part of the path to specific objects.

    # /<public_key>
    #              /<id_>
    """

    def getChild(self, path, request):
        return SpecificChannelEndpoint(self.session, self.channel_pk, path)

    def __init__(self, session, path):
        ChannelsEndpointBase.__init__(self, session)
        if path == b"mychannel":
            self.channel_pk = self.session.lm.mds.my_key.pub().key_to_bin()[10:]
        else:
            self.channel_pk = unhexlify(path)


class SpecificChannelEndpointBase(ChannelsEndpointBase):
    def __init__(self, session, channel_pk, path):
        self._logger = logging.getLogger(self.__class__.__name__)
        ChannelsEndpointBase.__init__(self, session)
        self.channel_pk = channel_pk
        self.channel_id = int(path)


class SpecificChannelEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint that serves contents of specific channels.

    # /<id>
    #      /torrents
    #      /commit
    """

    def __init__(self, session, channel_pk, path):
        SpecificChannelEndpointBase.__init__(self, session, channel_pk, path)

        self.putChild(b"torrents", SpecificChannelTorrentsEndpoint(session, self.channel_pk, self.channel_id))
        self.putChild(b"commit", SpecificChannelCommitEndpoint(session, self.channel_pk, self.channel_id))
        self.putChild(b"channels", SpecificChannelChannelsEndpoint(session, self.channel_pk, self.channel_id))
        self.putChild(b"collections", SpecificChannelCollectionsEndpoint(session, self.channel_pk, self.channel_id))
        self.putChild(b"copy", SpecificChannelCopyEndpoint(session, self.channel_pk, self.channel_id))

    # Get the list of the channel's contents (torrents/channels/etc.)
    def render_GET(self, request):
        args = recursive_unicode(request.args)
        sanitized = self.sanitize_parameters(args)
        include_total = args['include_total'][0] if 'include_total' in args else ''
        sanitized.update({"channel_pk": self.channel_pk, "origin_id": self.channel_id})

        with db_session:
            contents = self.session.lm.mds.MetadataNode.get_entries(**sanitized)
            contents_list = [c.to_simple_dict() for c in contents]
            total = self.session.lm.mds.MetadataNode.get_total_count(**sanitized) if include_total else None
        response_dict = {
            "results": contents_list,
            "first": sanitized['first'],
            "last": sanitized['last'],
            "sort_by": sanitized['sort_by'],
            "sort_desc": int(sanitized['sort_desc']),
        }
        if total is not None:
            response_dict.update({"total": total})

        return json.twisted_dumps(response_dict)


class SpecificChannelCopyEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint to create copy objects in a specific channel.

    # /copy
    """

    # Create a copy of an entry/entries from another channel
    @db_session
    def render_POST(self, request):
        personal_root = self.channel_id == 0 and self.channel_pk == self.session.lm.mds.my_key.pub().key_to_bin()[10:]
        # TODO: better error handling
        target_collection = self.session.lm.mds.CollectionNode.get(
            public_key=database_blob(self.channel_pk), id_=self.channel_id
        )
        try:
            request_parsed = json.twisted_loads(request.content.read())
        except ValueError:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "Bad JSON"})

        if not target_collection and not personal_root:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "Target channel not found"})
        results_list = []
        for entry in request_parsed:
            public_key, id_ = database_blob(unhexlify(entry["public_key"])), entry["id"]
            source = self.session.lm.mds.ChannelNode.get(public_key=public_key, id_=id_)
            if not source:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "Source entry not found"})
            # We must upgrage Collections to Channels when moving them to root channel, and, vice-versa,
            # downgrade Channels to Collections when moving them into existing channels
            if isinstance(source, self.session.lm.mds.CollectionNode):
                src_dict = source.to_dict()
                if self.channel_id == 0:
                    rslt = self.session.lm.mds.ChannelMetadata.create_channel(title=source.title)
                else:
                    dst_dict = {'origin_id': self.channel_id, "status": NEW}
                    for k in self.session.lm.mds.CollectionNode.nonpersonal_attributes:
                        dst_dict[k] = src_dict[k]
                    dst_dict.pop("metadata_type")
                    rslt = self.session.lm.mds.CollectionNode(**dst_dict)
                for child in source.actual_contents:
                    child.make_copy(rslt.id_)
            else:
                rslt = source.make_copy(self.channel_id)
            results_list.append(rslt.to_simple_dict())
        return json.twisted_dumps(results_list)


class SpecificChannelChannelsEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint that serves sub-channel for a specific channel.
    Currently, the only correct usage for this is to use it to create top-level personal channels.

    # /channels
    """

    # Create a new channel entry in this channel
    @db_session
    def render_POST(self, request):
        md = self.session.lm.mds.ChannelMetadata.create_channel("New channel", origin_id=self.channel_id)
        return json.twisted_dumps({"results": [md.to_simple_dict()]})


class SpecificChannelCollectionsEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint that serves collection objects for a specific channel.

    # /collections
    """

    # Create a new collection entry in this channel
    @db_session
    def render_POST(self, request):
        md = self.session.lm.mds.CollectionNode(origin_id=self.channel_id, title="New collection", status=NEW)
        return json.twisted_dumps({"results": [md.to_simple_dict()]})


class SpecificChannelTorrentsEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint that serves torrent objects for a specific channel.

    # /torrents
    """

    def return_500(self, request, exception):
        self._logger.exception(exception)
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        return json.twisted_dumps(
            {u"error": {u"handled": True, u"code": exception.__class__.__name__, u"message": str(exception)}}
        )

    # Put a torrent into the channel.
    def render_PUT(self, request):
        """
        .. http:put:: /channels/<public_key>/<id_>/torrents

        Add a torrent file to your own channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel. The torrent data is passed as base-64 encoded
        string. The description is optional.

        Option torrents_dir adds all .torrent files from a chosen directory
        Option recursive enables recursive scanning of the chosen directory for .torrent files

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel/torrents
                --data "torrent=...&description=funny video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                }

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel/torrents? --data "torrents_dir=some_dir&recursive=1"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": 13
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the passed torrent data is corrupt.
        """

        with db_session:
            channel = self.session.lm.mds.CollectionNode.get(
                public_key=database_blob(self.channel_pk), id_=self.channel_id
            )
        if not channel:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "Unknown channel"})

        parameters = recursive_unicode(http.parse_qs(request.content.read(), 1))

        if 'description' not in parameters or not parameters['description']:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        # This is required to determine if the connection can be closed by the server
        can_close = [True]

        def _faulty_req_termination(failure, can_close):
            # If this callback was triggered, then the connection is guaranteed to have been closed.
            can_close[0] = False
            if failure is not None:
                failure.trap(ConnectionDone)
                self._logger.exception("Connection did not close properly: %s %s", failure.getErrorMessage(),
                                       failure.type)

        request.notifyFinish().addBoth(_faulty_req_termination, can_close)
        def _on_url_fetched(data):
            return TorrentDef.load_from_memory(data)

        def _on_magnet_fetched(meta_info):
            if not meta_info:
                request.write(self.return_500(request, RuntimeError("Metainfo timeout")))
                if can_close[0]:
                    request.finish()
                return

            return TorrentDef.load_from_dict(meta_info)

        def _on_torrent_def_loaded(torrent_def):
            if not torrent_def:
                return
            channel.add_torrent_to_channel(torrent_def, extra_info)
            return 1

        def _on_added(added):
            request.write(json.twisted_dumps({"added": added}))
            if can_close[0]:
                request.finish()

        def _on_add_failed(failure):
            failure.trap(ValueError, DuplicateTorrentFileError, SchemeNotSupported)
            self._logger.exception(failure.value)
            request.write(self.return_500(request, failure.value))
            if can_close[0]:
                request.finish()

        # First, check whether we did upload a magnet link or URL
        if 'uri' in parameters and parameters['uri']:
            deferred = Deferred()
            uri = parameters['uri'][0]
            if uri.startswith("http:") or uri.startswith("https:"):
                deferred = http_get(uri)
                deferred.addCallback(_on_url_fetched)
            elif uri.startswith("magnet:"):
                _, xt, _ = parse_magnetlink(uri)
                if (
                    xt
                    and is_infohash(codecs.encode(xt, 'hex'))
                    and (channel.torrent_exists(xt) or channel.copy_torrent_from_infohash(xt))
                ):
                    return json.dumps({"added": 1})

                deferred.addCallback(_on_magnet_fetched)
                self.session.lm.ltmgr.get_metainfo(xt, timeout=30).addCallback(deferred.callback)
            else:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "unknown uri type"})

            deferred.addCallback(_on_torrent_def_loaded)
            deferred.addCallback(_on_added)
            deferred.addErrback(_on_add_failed)
            return NOT_DONE_YET

        torrents_dir = None
        if 'torrents_dir' in parameters and parameters['torrents_dir']:
            torrents_dir = parameters['torrents_dir'][0]
            if not os.path.isabs(torrents_dir):
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "the torrents_dir should point to a directory"})

        recursive = False
        if 'recursive' in parameters and parameters['recursive']:
            recursive = parameters['recursive'][0]
            if not torrents_dir:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps(
                    {"error": "the torrents_dir parameter should be provided when the recursive " "parameter is set"}
                )

        if torrents_dir:
            torrents_list, errors_list = channel.add_torrents_from_dir(torrents_dir, recursive)
            return json.twisted_dumps({"added": len(torrents_list), "errors": errors_list})

        if 'torrent' not in parameters or not parameters['torrent']:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "torrent parameter missing"})

        # Try to parse the torrent data
        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
            channel.add_torrent_to_channel(torrent_def, extra_info)
        except (TypeError, ValueError, DuplicateTorrentFileError) as e:
            _on_add_failed(e)
        return json.twisted_dumps({"added": 1})


class SpecificChannelCommitEndpoint(SpecificChannelEndpointBase):
    """
    The endpoint to trigger commit events by POSTing commit objects.

    # /commit
    """

    def render_POST(self, request):
        with db_session:
            if self.channel_id == 0:
                for t in self.session.lm.mds.CollectionNode.commit_all_channels():
                    self.session.lm.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(t))
            else:
                coll = self.session.lm.mds.CollectionNode.get(
                    public_key=database_blob(self.channel_pk), id_=self.channel_id
                )
                if not coll:
                    request.setResponseCode(http.NOT_FOUND)
                    return json.twisted_dumps({"success": False})
                torrent_dict = coll.commit_channel_torrent()
                if torrent_dict:
                    self.session.lm.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(torrent_dict))

        return json.twisted_dumps({"success": True})

    def render_GET(self, request):
        with db_session:
            dirty = self.session.lm.mds.MetadataNode.exists(
                lambda g: g.public_key == database_blob(self.channel_pk) and g.status in DIRTY_STATUSES
            )
            return json.twisted_dumps({"dirty": dirty})
