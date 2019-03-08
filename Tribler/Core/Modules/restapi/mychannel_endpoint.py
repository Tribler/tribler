from __future__ import absolute_import

import base64
import json
import logging
import os
from binascii import hexlify, unhexlify

from pony.orm import db_session

from six.moves.urllib.parse import unquote

from twisted.internet.defer import Deferred
from twisted.web import http, resource
from twisted.web.error import SchemeNotSupported
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi.metadata_endpoint import SpecificChannelTorrentsEndpoint
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import http_get
from Tribler.Core.exceptions import DuplicateTorrentFileError
from Tribler.pyipv8.ipv8.database import database_blob


class BaseMyChannelEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

    def return_500(self, request, exception):
        self._logger.exception(exception)
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        return json.dumps({
            u"error": {
                u"handled": True,
                u"code": exception.__class__.__name__,
                u"message": exception.message
            }
        })


class MyChannelEndpoint(BaseMyChannelEndpoint):

    def __init__(self, session):
        BaseMyChannelEndpoint.__init__(self, session)
        self.putChild("torrents", MyChannelTorrentsEndpoint(session))
        self.putChild("commit", MyChannelCommitEndpoint(session))

    def render_GET(self, request):
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            return json.dumps({
                'mychannel': {
                    'public_key': hexlify(my_channel.public_key),
                    'name': my_channel.title,
                    'description': my_channel.tags,
                    'dirty': my_channel.dirty
                }
            })

    def render_POST(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'name' not in parameters and 'description' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name or description parameter missing"})

        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            my_channel.update_metadata(update_dict={
                "tags": unquote(parameters['description'][0]).decode('utf-8'),
                "title": unquote(parameters['name'][0]).decode('utf-8')
            })

        return json.dumps({"edited": True})

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or not parameters['name'] or not parameters['name'][0]:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "channel name cannot be empty"})

        if 'description' not in parameters or not parameters['description']:
            description = u''
        else:
            description = unquote(parameters['description'][0]).decode('utf-8')

        my_key = self.session.trustchain_keypair
        my_channel_pk = my_key.pub().key_to_bin()

        # Do not allow to add a channel twice
        if self.session.lm.mds.get_my_channel():
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "channel already exists"})

        title = unquote(parameters['name'][0]).decode('utf-8')
        self.session.lm.mds.ChannelMetadata.create_channel(title, description)
        return json.dumps({
            "added": hexlify(str(my_channel_pk)),
        })


class MyChannelTorrentsEndpoint(BaseMyChannelEndpoint):

    def getChild(self, path, request):
        return MyChannelSpecificTorrentEndpoint(self.session, path)

    def render_GET(self, request):
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            sanitized = SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)
            if 'exclude_deleted' in request.args:
                sanitized['exclude_deleted'] = request.args['exclude_deleted']

            torrents, total = self.session.lm.mds.TorrentMetadata.get_entries(
                channel_pk=database_blob(my_channel.public_key), **sanitized)
            torrents = [torrent.to_simple_dict() for torrent in torrents]

            return json.dumps({
                "torrents": torrents,
                "first": sanitized['first'],
                "last": sanitized['last'],
                "sort_by": sanitized['sort_by'],
                "sort_asc": int(sanitized['sort_asc']),
                "total": total,
                "dirty": my_channel.dirty
            })

    def render_POST(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'status' not in parameters or 'infohashes' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "status or infohashes parameter missing"})

        new_status = int(parameters['status'][0])
        infohashes = parameters['infohashes'][0].split(',')

        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            for infohash in infohashes:
                torrent = my_channel.get_torrent(unhexlify(infohash))
                if not torrent:
                    continue
                torrent.status = new_status

        return json.dumps({"success": True})

    def render_DELETE(self, request):
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            my_channel.drop_channel_contents()

        return json.dumps({"success": True})

    @db_session
    def render_PUT(self, request):
        """
        .. http:put:: /mychannel/torrents

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
        my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
        if not my_channel:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "your channel has not been created yet"})

        parameters = http.parse_qs(request.content.read(), 1)

        if 'description' not in parameters or not parameters['description']:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        def _on_url_fetched(data):
            return TorrentDef.load_from_memory(data)

        def _on_magnet_fetched(meta_info):
            return TorrentDef.load_from_dict(meta_info)

        def _on_torrent_def_loaded(torrent_def):
            with db_session:
                channel = self.session.lm.mds.get_my_channel()
                channel.add_torrent_to_channel(torrent_def, extra_info)
            return 1

        def _on_added(added):
            request.write(json.dumps({"added": added}))
            request.finish()

        def _on_add_failed(failure):
            failure.trap(ValueError, DuplicateTorrentFileError, SchemeNotSupported)
            self._logger.exception(failure.value)
            request.write(self.return_500(request, failure.value))
            request.finish()

        def _on_timeout(_):
            request.write(self.return_500(request, RuntimeError("Metainfo timeout")))
            request.finish()

        # First, check whether we did upload a magnet link or URL
        if 'uri' in parameters and parameters['uri']:
            deferred = Deferred()
            uri = parameters['uri'][0]
            if uri.startswith("http:") or uri.startswith("https:"):
                deferred = http_get(uri)
                deferred.addCallback(_on_url_fetched)
            elif uri.startswith("magnet:"):
                try:
                    self.session.lm.ltmgr.get_metainfo(uri, callback=deferred.callback,
                                                       timeout=30, timeout_callback=_on_timeout, notify=True)
                except Exception as ex:
                    deferred.errback(ex)

                deferred.addCallback(_on_magnet_fetched)
            else:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "unknown uri type"})

            deferred.addCallback(_on_torrent_def_loaded)
            deferred.addCallback(_on_added)
            deferred.addErrback(_on_add_failed)
            return NOT_DONE_YET

        torrents_dir = None
        if 'torrents_dir' in parameters and parameters['torrents_dir'] > 0:
            torrents_dir = parameters['torrents_dir'][0]
            if not os.path.isabs(torrents_dir):
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the torrents_dir should point to a directory"})

        recursive = False
        if 'recursive' in parameters and parameters['recursive'] > 0:
            recursive = parameters['recursive'][0]
            if not torrents_dir:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "the torrents_dir parameter should be provided when the recursive "
                                            "parameter is set"})

        if torrents_dir:
            torrents_list, errors_list = my_channel.add_torrents_from_dir(torrents_dir, recursive)
            return json.dumps({"added": len(torrents_list), "errors": errors_list})

        if 'torrent' not in parameters or not parameters['torrent']:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "torrent parameter missing"})

        # Try to parse the torrent data
        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
        except (TypeError, ValueError):
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            return json.dumps({"error": "invalid torrent file"})

        try:
            my_channel.add_torrent_to_channel(torrent_def, extra_info)
        except DuplicateTorrentFileError:
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            return json.dumps({"error": "this torrent already exists in your channel"})

        return json.dumps({"added": 1})


class MyChannelSpecificTorrentEndpoint(BaseMyChannelEndpoint):

    def __init__(self, session, infohash):
        BaseMyChannelEndpoint.__init__(self, session)
        self.infohash = unhexlify(infohash)

    @db_session
    def render_PATCH(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'status' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "status parameter missing"})

        my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
        if not my_channel:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "your channel has not been created"})

        torrent = my_channel.get_torrent(self.infohash)
        if not torrent:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "torrent with the specified infohash could not be found"})

        new_status = int(parameters['status'][0])
        torrent.status = new_status

        return json.dumps({"success": True, "new_status": new_status, "dirty": my_channel.dirty})


class MyChannelCommitEndpoint(BaseMyChannelEndpoint):

    def render_POST(self, request):
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if not my_channel:
                request.setResponseCode(http.NOT_FOUND)
                return json.dumps({"error": "your channel has not been created"})

            torrent_dict = my_channel.commit_channel_torrent()
            if torrent_dict:
                self.session.lm.gigachannel_manager.updated_my_channel(TorrentDef.load_from_dict(torrent_dict))

        return json.dumps({"success": True})
