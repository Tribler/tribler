import json
import os
from binascii import unhexlify, hexlify

from pony.orm import db_session
from twisted.web import resource, http

from Tribler.Core.Modules.restapi.metadata_endpoint import SpecificChannelTorrentsEndpoint


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
                "tags": parameters['name'][0].encode('utf-8'),
                "title": parameters['description'][0].encode('utf-8')
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
            description = str(parameters['description'][0]).encode('utf-8')

        my_key = self.session.trustchain_keypair
        my_channel_pk = my_key.pub().key_to_bin()

        # Do not allow to add a channel twice
        if self.session.lm.mds.get_my_channel():
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "channel already exists"})

        title = str(parameters['name'][0]).encode('utf-8')
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
            torrents = [torrent.to_simple_dict(include_status=True) for torrent in torrents]

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


class MyChannelSpecificTorrentEndpoint(BaseMyChannelEndpoint):

    def __init__(self, session, infohash):
        BaseMyChannelEndpoint.__init__(self, session)
        self.infohash = unhexlify(infohash)

    def render_PATCH(self, request):
        parameters = http.parse_qs(request.content.read(), 1)
        if 'status' not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "status parameter missing"})

        with db_session:
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

        return json.dumps({"success": True, "new_status": new_status})


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
