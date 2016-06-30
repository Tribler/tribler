import json
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json


class ChannelsPlaylistsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for handling requests regarding playlists in a channel.
    """
    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)/playlists

        Returns the playlists in your channel. Returns error 404 if you have not created a channel.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered/abcd/playlists

            **Example response**:

            .. sourcecode:: javascript

                {
                    "playlists": [{
                        "id": 1,
                        "name": "My first playlist",
                        "description": "Funny movies",
                        "torrents": [{
                            "id": 4,
                            "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
                            "name": "Ubuntu-16.04-desktop-amd64",
                            "size": 8592385,
                            "category": "other",
                            "num_seeders": 42,
                            "num_leechers": 184,
                            "last_tracker_check": 1463176959
                        }, ... ]
                    }, ...]
                }

            :statuscode 404: if you have not created a channel.
        """

        channel = self.get_channel_from_db(self.cid)
        if channel is None:
            return ChannelsPlaylistsEndpoint.return_404(request)

        playlists = []
        req_columns = ['Playlists.id', 'Playlists.name', 'Playlists.description']
        req_columns_torrents = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                                'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']
        for playlist in self.channel_db_handler.getPlaylistsFromChannelId(channel[0], req_columns):
            # Fetch torrents in the playlist
            playlist_torrents = self.channel_db_handler.getTorrentsFromPlaylist(playlist[0], req_columns_torrents)
            torrents = [convert_db_torrent_to_json(torrent_result) for torrent_result in playlist_torrents
                        if torrent_result[2] is not None]

            playlists.append({"id": playlist[0], "name": playlist[1], "description": playlist[2], "torrents": torrents})

        return json.dumps({"playlists": playlists})
