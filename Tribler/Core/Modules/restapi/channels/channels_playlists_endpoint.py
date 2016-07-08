import json

from twisted.web import http

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

    def getChild(self, path, request):
        return ChannelsModifyPlaylistsEndpoint(self.session, self.cid, path)

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

    def render_PUT(self, request):
        """
        .. http:put:: /channels/discovered/(string: channelid)/playlists

        Create a new empty playlist with a given name and description. The name and description parameters are
        mandatory.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered/abcd/playlists
                --data "name=My fancy playlist&description=This playlist contains some random movies"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "created": True
                }

            :statuscode 400: if you are missing the name and/or description parameter
            :statuscode 404: if the specified channel does not exist
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "description parameter missing"})

        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsPlaylistsEndpoint.return_404(request)

        channel_community = self.get_community_for_channel_id(channel_info[0])
        if channel_community is None:
            return BaseChannelsEndpoint.return_404(request,
                                                   message="the community for the specific channel cannot be found")

        channel_community.create_playlist(parameters['name'][0], parameters['description'][0], [])

        return json.dumps({"created": True})


class ChannelsModifyPlaylistsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for requests that are modifying a specific playlist in a channel.
    """

    def __init__(self, session, cid, playlist_id):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.playlist_id = playlist_id

    def render_DELETE(self, request):
        """
        .. http:delete:: /channels/discovered/(string: channelid)/playlists/(int: playlistid)

        Remove a playlist with a specified playlist id.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/channels/discovered/abcd/playlists/3

            **Example response**:

            .. sourcecode:: javascript

                {
                    "removed": True
                }

            :statuscode 404: if the specified channel (community) or playlist does not exist
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsPlaylistsEndpoint.return_404(request)

        playlist = self.channel_db_handler.getPlaylist(self.playlist_id, ['Playlists.dispersy_id', 'Playlists.id'])
        if playlist is None:
            return BaseChannelsEndpoint.return_404(request, message="this playlist cannot be found")

        channel_community = self.get_community_for_channel_id(channel_info[0])
        if channel_community is None:
            return BaseChannelsEndpoint.return_404(request,
                                                   message="the community for the specific channel cannot be found")

        # Remove all torrents from this playlist
        playlist_torrents = self.channel_db_handler.get_torrent_ids_from_playlist(playlist[1])
        channel_community.remove_playlist_torrents(playlist[0], [dispersy_id for dispersy_id, in playlist_torrents])

        # Remove the playlist itself
        channel_community.remove_playlists([playlist[0]])

        return json.dumps({"removed": True})
