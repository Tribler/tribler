from __future__ import absolute_import

import base64
import json
import os
import sys
import urllib
from binascii import unhexlify, hexlify

from pony.orm import db_session
from twisted.web import resource, http

from Tribler.Core.Modules.restapi.metadata_endpoint import SpecificChannelTorrentsEndpoint
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateTorrentFileError


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


class BaseMyChannelEndpoint(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session


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
                "tags": urllib.unquote(parameters['description'][0]).decode('utf-8'),
                "title": urllib.unquote(parameters['name'][0]).decode('utf-8')
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
            description = urllib.unquote(parameters['description'][0]).decode('utf-8')

        my_key = self.session.trustchain_keypair
        my_channel_pk = my_key.pub().key_to_bin()

        # Do not allow to add a channel twice
        if self.session.lm.mds.get_my_channel():
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "channel already exists"})

        title = urllib.unquote(parameters['name'][0]).decode('utf-8')
        self.session.lm.mds.ChannelMetadata.create_channel(title, description)
        return json.dumps({
            "added": str(my_channel_pk).encode("hex"),
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

            request.args['channel'] = [str(my_channel.public_key).encode('hex')]
            first, last, sort_by, sort_asc, query_filter, channel = \
                SpecificChannelTorrentsEndpoint.sanitize_parameters(request.args)

            torrents, total = self.session.lm.mds.TorrentMetadata.get_torrents(
                first, last, sort_by, sort_asc, query_filter, channel)
            torrents = [torrent.to_simple_dict() for torrent in torrents]

            return json.dumps({
                "torrents": torrents,
                "first": first,
                "last": last,
                "sort_by": sort_by,
                "sort_asc": int(sort_asc),
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

            # Remove all torrents in your channel
            torrents = my_channel.contents_list
            for torrent in torrents:
                my_channel.delete_torrent(torrent.infohash)

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
                return json.dumps({"the torrents_dir parameter should be provided when the rec"})

        if torrents_dir:
            torrents_list = []
            errors_list = []

            if recursive:
                def rec_gen():
                    for root, _, filenames in os.walk(torrents_dir):
                        for fn in filenames:
                            yield os.path.join(root, fn)

                filename_generator = rec_gen()
            else:
                filename_generator = os.listdir(torrents_dir)

            # Build list of .torrents to process
            for f in filename_generator:
                filepath = os.path.join(torrents_dir, f)
                filename = str(filepath) if sys.platform == 'win32' else filepath.decode('utf-8')
                if os.path.isfile(filepath) and filename.endswith(u'.torrent'):
                    torrents_list.append(filepath)

            for chunk in chunks(torrents_list, 100):  # 100 is a reasonable chunk size for commits
                with db_session:
                    for f in chunk:
                        try:
                            my_channel.add_torrent_to_channel(TorrentDef.load(f), {})
                        except DuplicateTorrentFileError:
                            pass
                        except:
                            errors_list.append(f)

            return json.dumps({"added": len(torrents_list), "errors": errors_list})

        if 'torrent' not in parameters or len(parameters['torrent']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "torrent parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        # Try to parse the torrent data
        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
        except ValueError:
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

            my_channel.commit_channel_torrent()
            torrent_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".torrent")
            self.session.lm.gigachannel_manager.updated_my_channel(torrent_path)

        return json.dumps({"success": True})
