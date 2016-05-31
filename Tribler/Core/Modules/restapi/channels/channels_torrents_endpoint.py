import json

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json


class ChannelsTorrentsEndpoint(BaseChannelsEndpoint):
    """
    A GET request to this endpoint returns all discovered torrents in a specific channel. The size of the torrent is
    in number of bytes. The last_tracker_check value will be 0 if we did not check the tracker state of the torrent yet.

    Example GET response:
    {
        "torrents": [{
            "id": 4,
            "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
            "name": "Ubuntu-16.04-desktop-amd64",
            "size": 8592385,
            "category": "other",
            "num_seeders": 42,
            "num_leechers": 184,
            "last_tracker_check": 1463176959,
            "added": 1461840601
        }, ...]
    }
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def render_GET(self, request):
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsTorrentsEndpoint.return_404(request)

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                              'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']
        results_local_torrents_channel = self.channel_db_handler\
            .getTorrentsFromChannelId(channel_info[0], True, torrent_db_columns)

        results_json = [convert_db_torrent_to_json(torrent_result) for torrent_result in results_local_torrents_channel]
        return json.dumps({"torrents": results_json})
