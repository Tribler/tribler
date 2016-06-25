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
                              "rssfeeds": MyChannelRssFeedsEndpoint,
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

    def render_PUT(self, request):
        """
        .. http:put:: /mychannel

        Create your own new channel. The passed mode and descriptions are optional.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel
                --data "name=fancy name&description=fancy description&mode=open"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": 23
                }

            :statuscode 500: if a channel with the specified name already exists.
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "name parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            description = u''
        else:
            description = parameters['description'][0]

        if 'mode' not in parameters or len(parameters['mode']) == 0:
            mode = u'closed'
        else:
            mode = parameters['mode'][0]

        try:
            channel_id = self.session.create_channel(parameters['name'][0], description, mode)
        except DuplicateChannelNameError as ex:
            return MyChannelBaseEndpoint.return_500(self, request, ex)

        return json.dumps({"added": channel_id})


class MyChannelTorrentsEndpoint(MyChannelBaseEndpoint):
    """
    This end is responsible for handling requests regarding torrents in your channel.
    """

    def getChild(self, path, request):
        return MyChannelModifyTorrentsEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /mychannel/torrents

        Return the torrents in your channel. For each torrent item, the infohash, name and timestamp added is included.
        This endpoint returns a 404 HTTP response if you have not created a channel (yet).

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/mychannel/torrents

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrents": [{
                        "name": "ubuntu-15.04.iso",
                        "added": 1461840601,
                        "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
                    }, ...]
                }

            :statuscode 404: if your channel does not exist.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        req_columns = ['ChannelTorrents.name', 'infohash', 'ChannelTorrents.inserted']
        torrents = self.channel_db_handler.getTorrentsFromChannelId(my_channel_id, True, req_columns)

        torrent_list = []
        for torrent in torrents:
            torrent_list.append({'name': torrent[0], 'infohash': torrent[1].encode('hex'), 'added': torrent[2]})
        return json.dumps({'torrents': torrent_list})

    def render_PUT(self, request):
        """
        .. http:put:: /mychannel/torrents

        Add a torrent file to your own channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel. The torrent data is passed as base-64 encoded
        string. The description is optional.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel/torrents --data "torrent=...&description=funny video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the passed torrent data is corrupt.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if 'torrent' not in parameters or len(parameters['torrent']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "torrent parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
            self.session.add_torrent_def_to_channel(my_channel_id, torrent_def, extra_info, forward=True)

        except (DuplicateTorrentFileError, ValueError) as ex:
            return MyChannelBaseEndpoint.return_500(self, request, ex)

        return json.dumps({"added": True})


class MyChannelModifyTorrentsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for methods that modify the list of torrents (adding/removing torrents).
    """

    def __init__(self, session, torrent_url):
        MyChannelBaseEndpoint.__init__(self, session)
        self.torrent_url = torrent_url

    def render_PUT(self, request):
        """
        .. http:put:: /mychannel/torrents/http%3A%2F%2Ftest.com%2Ftest.torrent

        Add a torrent by magnet or url to your channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel (except with magnet links).

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel/torrents/http%3A%2F%2Ftest.com%2Ftest.torrent
                            --data "description=nice video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": "http://test.com/test.torrent"
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the specified torrent is already in your channel.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        if my_channel_id is None:
            return MyChannelBaseEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        try:
            if self.torrent_url.startswith("http:") or self.torrent_url.startswith("https:"):
                torrent_def = TorrentDef.load_from_url(self.torrent_url)
                self.session.add_torrent_def_to_channel(my_channel_id, torrent_def, extra_info, forward=True)
            if self.torrent_url.startswith("magnet:"):

                def on_receive_magnet_meta_info(meta_info):
                    torrent_def = TorrentDef.load_from_dict(meta_info)
                    self.session.add_torrent_def_to_channel(my_channel_id, torrent_def, extra_info, forward=True)

                infohash_or_magnet = self.torrent_url
                callback = on_receive_magnet_meta_info
                self.session.lm.ltmgr.get_metainfo(infohash_or_magnet, callback)

        except (DuplicateTorrentFileError, ValueError) as ex:
            return MyChannelBaseEndpoint.return_500(self, request, ex)

        return json.dumps({"added": self.torrent_url})


class MyChannelRssFeedsEndpoint(MyChannelBaseEndpoint):
    """
    This endpoint is responsible for handling requests regarding rss feeds in your channel.
    """

    def getChild(self, path, request):
        return MyChannelModifyRssFeedsEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /mychannel/rssfeeds

        Return the RSS feeds in your channel.

            .. sourcecode:: none

                curl -X GET http://localhost:8085/mychannel/rssfeeds

            **Example response**:

            .. sourcecode:: javascript

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
        feeds_list = [{'url': rss_item} for rss_item in rss_list]

        return json.dumps({"rssfeeds": feeds_list})


class MyChannelRecheckFeedsEndpoint(MyChannelBaseEndpoint):
    """
    This class is responsible for handling requests regarding refreshing rss feeds in your channel.
    """

    def render_POST(self, request):
        """
        .. http:post:: /mychannel/recheckfeeds

        Rechecks all rss feeds in your channel. Returns error 404 if you channel does not exist.

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/mychannel/recheckrssfeeds

            **Example response**:

            .. sourcecode:: javascript

                {
                    "rechecked": True
                }

            :statuscode 404: if you have not created a channel.
        """
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
        .. http:put:: /mychannel/rssfeeds/http%3A%2F%2Ftest.com%2Frss.xml

        Add a RSS feed to your channel. Returns error 409 if the supplied RSS feed already exists.
        Note that the rss feed url should be URL-encoded.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/mychannel/rssfeeds/http%3A%2F%2Ftest.com%2Frss.xml

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                }

            :statuscode 409: (conflict) if the specified RSS URL is already present in your feeds.
        """
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
        .. http:delete:: /mychannel/rssfeeds/http%3A%2F%2Ftest.com%2Frss.xml

        Delete a RSS feed from your channel. Returns error 404 if the RSS feed that is being removed does not exist.
        Note that the rss feed url should be URL-encoded.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/mychannel/rssfeeds/http%3A%2F%2Ftest.com%2Frss.xml

            **Example response**:

            .. sourcecode:: javascript

                {
                    "removed": True
                }

            :statuscode 404: if the specified RSS URL is not in your feed list.
        """
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
