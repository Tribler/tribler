import json
from twisted.web import http, resource
from Tribler.Core.CacheDB.sqlitecachedb import str2bin

from Tribler.Core.simpledefs import NTFY_CHANNELCAST


class MyChannelBaseEndpoint(resource.Resource):
    """
    Base class for all endpoints related to fetching information about my channel.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    @staticmethod
    def return_404(request, message="your channel has not been created"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})

    def get_my_channel_object(self):
        """
        Returns the Channel object associated with you channel that is used to manage rss feeds.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        return self.session.lm.channel_manager.get_my_channel(my_channel_id)


class MyChannelEndpoint(MyChannelBaseEndpoint):
    """
    This endpoint is responsible for handing all requests regarding your channel such as getting and updating
    torrents, playlists and rss-feeds.
    """
    def __init__(self, session):
        MyChannelBaseEndpoint.__init__(self, session)
        child_handler_dict = {"overview": MyChannelOverviewEndpoint, "torrents": MyChannelTorrentsEndpoint,
                              "rssfeeds": MyChannelRssFeedsEndpoint, "playlists": MyChannelPlaylistsEndpoint,
                              "recheckfeeds": MyChannelRecheckFeedsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))


class MyChannelOverviewEndpoint(MyChannelBaseEndpoint):
    """
    Return the name, description and identifier of your channel.
    This endpoint returns a 404 HTTP response if you have not created a channel (yet).

    Example response:
    {
        "overview": {
            "name": "My Tribler channel",
            "description": "A great collection of open-source movies",
            "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
        }
    }
    """

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        my_channel = self.channel_db_handler.getChannel(my_channel_id)
        request.setHeader('Content-Type', 'text/json')
        return json.dumps({'overview': {'identifier': my_channel[1].encode('hex'), 'name': my_channel[2],
                                        'description': my_channel[3]}})


class MyChannelTorrentsEndpoint(MyChannelBaseEndpoint):
    """
    Return the torrents in your channel. For each torrent item, the infohash, name and timestamp added is included.
    This endpoint returns a 404 HTTP response if you have not created a channel (yet).

    Example response:
    {
        "torrents": [{
            "name": "ubuntu-15.04.iso",
            "added": 1461840601,
            "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
        }, ...]
    }
    """

    def render_GET(self, request):
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        req_columns = ['ChannelTorrents.name', 'infohash', 'ChannelTorrents.inserted']
        torrents = self.channel_db_handler.getTorrentsFromChannelId(my_channel_id, True, req_columns)

        request.setHeader('Content-Type', 'text/json')
        torrent_list = []
        for torrent in torrents:
            torrent_list.append({'name': torrent[0], 'infohash': torrent[1].encode('hex'), 'added': torrent[2]})
        return json.dumps({'torrents': torrent_list})


class MyChannelRssFeedsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for handling requests regarding rss feeds in your channel.
    """

    def getChild(self, path, request):
        return MyChannelModifyRssFeedsEndpoint(self.session, path)

    def render_GET(self, request):
        """
        Return the RSS feeds in your channel.

        Example response:
        {
            "rssfeeds": [{
                "url": "http://rssprovider.com/feed.xml",
            }, ...]
        }
        """
        channel_obj = self.get_my_channel_object()
        if channel_obj is None:
            return MyChannelBaseEndpoint.return_404(request)

        rss_list = channel_obj.get_rss_feed_url_list()
        request.setHeader('Content-Type', 'text/json')
        feeds_list = [{'url': rss_item} for rss_item in rss_list]

        return json.dumps({"rssfeeds": feeds_list})


class MyChannelRecheckFeedsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for handling requests regarding refreshing rss feeds in your channel.
    """

    def render_POST(self, request):
        """
        Rechecks all rss feeds in your channel. Returns error 404 if you channel does not exist.
        """
        request.setHeader('Content-Type', 'text/json')

        channel_obj = self.get_my_channel_object()
        if channel_obj is None:
            return MyChannelBaseEndpoint.return_404(request)

        channel_obj.refresh_all_feeds()

        return json.dumps({"rechecked": True})


class MyChannelModifyRssFeedsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for methods that modify the list of RSS feed URLs (adding/removing feeds).
    """

    def __init__(self, session, feed_url):
        MyChannelBaseEndpoint.__init__(self, session)
        self.feed_url = feed_url

    def render_PUT(self, request):
        """
        Add a RSS feed to your channel. Returns error 409 if the supplied RSS feed already exists.
        Note that the rss feed url should be URL-encoded.
        """
        request.setHeader('Content-Type', 'text/json')
        channel_obj = self.get_my_channel_object()
        if channel_obj is None:
            return MyChannelBaseEndpoint.return_404(request)

        if self.feed_url in channel_obj.get_rss_feed_url_list():
            request.setResponseCode(http.CONFLICT)
            return json.dumps({"error": "this rss feed already exists"})

        channel_obj.create_rss_feed(self.feed_url)
        return json.dumps({"added": True})

    def render_DELETE(self, request):
        """
        Delete a RSS feed from your channel. Returns error 404 if the RSS feed that is being removed does not exist.
        Note that the rss feed url should be URL-encoded.
        """
        request.setHeader('Content-Type', 'text/json')
        channel_obj = self.get_my_channel_object()
        if channel_obj is None:
            return MyChannelBaseEndpoint.return_404(request)

        if self.feed_url not in channel_obj.get_rss_feed_url_list():
            return MyChannelBaseEndpoint.return_404(request, message="this url is not added to your RSS feeds")

        channel_obj.remove_rss_feed(self.feed_url)
        return json.dumps({"removed": True})


class MyChannelPlaylistsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for handling requests regarding playlists in your channel.
    """

    def render_GET(self, request):
        """
        Returns the playlists in your channel. Returns error 404 if you have not created a channel.

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
        request.setHeader('Content-Type', 'text/json')

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
