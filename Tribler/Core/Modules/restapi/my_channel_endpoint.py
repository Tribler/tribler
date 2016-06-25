import json
import base64
import logging

from twisted.web import http, resource

from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Core.exceptions import DuplicateChannelNameError, DuplicateTorrentFileError


class MyChannelEndpoint(MyChannelBaseEndpoint):
    """
    This endpoint is responsible for handing all requests regarding your channel such as getting and updating
    torrents, playlists and rss-feeds.
    """

    def __init__(self, session):
        MyChannelBaseEndpoint.__init__(self, session)
        child_handler_dict = {"torrents": MyChannelTorrentsEndpoint,
                              "playlists": MyChannelPlaylistsEndpoint,
                              "recheckfeeds": MyChannelRecheckFeedsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))

    def render_GET(self, request):
        """
        .. http:get:: /mychannel

        Return the name, description and identifier of your channel.
        This endpoint returns a 404 HTTP response if you have not created a channel (yet).

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/mychannel

            **Example response**:

            .. sourcecode:: javascript

                {
                    "overview": {
                        "name": "My Tribler channel",
                        "description": "A great collection of open-source movies",
                        "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
                    }
                }

            :statuscode 404: if your channel has not been created (yet).
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        my_channel = self.channel_db_handler.getChannel(my_channel_id)
        return json.dumps({'overview': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                        'description': my_channel[3]}})


class MyChannelPlaylistsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for handling requests regarding playlists in your channel.
    """

    def render_GET(self, request):
        """
        .. http:get:: /mychannel/playlists

        Returns the playlists in your channel. Returns error 404 if you have not created a channel.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/mychannel/playlists

            **Example response**:

            .. sourcecode:: javascript

                {
                    "playlists": [{
                        "id": 1,
                        "name": "My first playlist",
                        "description": "Funny movies",
                        "torrents": [{
                            "name": "movie_1",
                            "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
                        }, ... ]
                    }, ...]
                }

            :statuscode 404: if you have not created a channel.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        playlists = []
        req_columns = ['Playlists.id', 'Playlists.name', 'Playlists.description']
        req_columns_torrents = ['ChannelTorrents.name', 'Torrent.infohash']
        for playlist in self.channel_db_handler.getPlaylistsFromChannelId(my_channel_id, req_columns):
            # Fetch torrents in the playlist
            torrents = []
            for torrent in self.channel_db_handler.getTorrentsFromPlaylist(playlist[0], req_columns_torrents):
                torrents.append({"name": torrent[0], "infohash": str2bin(torrent[1]).encode('hex')})

            playlists.append({"id": playlist[0], "name": playlist[1], "description": playlist[2], "torrents": torrents})

        return json.dumps({"playlists": playlists})
