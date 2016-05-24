import json
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint


class ChannelsPlaylistsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for handling requests regarding playlists in a channel.
    """
    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def render_GET(self, request):
        """
        Returns the playlists in a specific channel.

        Example response:
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
        """

        channel = self.get_channel_from_db(self.cid)
        if channel is None:
            return ChannelsPlaylistsEndpoint.return_404(request)

        playlists = []
        req_columns = ['Playlists.id', 'Playlists.name', 'Playlists.description']
        req_columns_torrents = ['ChannelTorrents.name', 'Torrent.infohash']
        for playlist in self.channel_db_handler.getPlaylistsFromChannelId(channel[0], req_columns):
            # Fetch torrents in the playlist
            torrents = []
            for torrent in self.channel_db_handler.getTorrentsFromPlaylist(playlist[0], req_columns_torrents):
                torrents.append({"name": torrent[0], "infohash": str2bin(torrent[1]).encode('hex')})

            playlists.append({"id": playlist[0], "name": playlist[1], "description": playlist[2], "torrents": torrents})

        return json.dumps({"playlists": playlists})
