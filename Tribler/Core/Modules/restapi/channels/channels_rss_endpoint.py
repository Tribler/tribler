import json
from twisted.web import http
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint


class BaseChannelsRssFeedsEndpoint(BaseChannelsEndpoint):

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def get_my_channel_obj_or_error(self, request):
        """
        Returns a tuple of (channel_obj, error). Callers of this method should check whether the channel_obj is None and
        if so, return the error.
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return None, BaseChannelsRssFeedsEndpoint.return_404(request)

        if channel_info[0] != self.channel_db_handler.getMyChannelId():
            return None, BaseChannelsRssFeedsEndpoint.return_401(request)

        channel_obj = self.get_my_channel_object()
        if channel_obj is None:
            return None, BaseChannelsRssFeedsEndpoint.return_404(request)

        return channel_obj, None


class ChannelsRssFeedsEndpoint(BaseChannelsRssFeedsEndpoint):
    """
    This class is responsible for handling requests regarding rss feeds in a channel.
    """

    def getChild(self, path, request):
        return ChannelModifyRssFeedEndpoint(self.session, self.cid, path)

    def render_GET(self, request):
        """
        Return the RSS feeds in a channel.

        Example response:
        {
            "rssfeeds": [{
                "url": "http://rssprovider.com/feed.xml",
            }, ...]
        }
        """
        channel_obj_dict = self.get_my_channel_obj_or_error(request)
        if channel_obj_dict[0] is None:
            return channel_obj_dict[1]

        rss_list = channel_obj_dict[0].get_rss_feed_url_list()
        request.setHeader('Content-Type', 'text/json')
        feeds_list = [{'url': rss_item} for rss_item in rss_list]

        return json.dumps({"rssfeeds": feeds_list})


class ChannelsRecheckFeedsEndpoint(BaseChannelsRssFeedsEndpoint):
    """
    This class is responsible for handling requests regarding refreshing rss feeds in your channel.
    """

    def render_POST(self, request):
        """
        Rechecks all rss feeds in your channel. Returns error 404 if you channel does not exist.
        """
        channel_obj_dict = self.get_my_channel_obj_or_error(request)
        if channel_obj_dict[0] is None:
            return channel_obj_dict[1]

        channel_obj_dict[0].refresh_all_feeds()

        return json.dumps({"rechecked": True})


class ChannelModifyRssFeedEndpoint(BaseChannelsRssFeedsEndpoint):
    """
    This class is responsible for methods that modify the list of RSS feed URLs (adding/removing feeds).
    """

    def __init__(self, session, cid, feed_url):
        BaseChannelsRssFeedsEndpoint.__init__(self, session, cid)
        self.feed_url = feed_url

    def render_PUT(self, request):
        """
        Add a RSS feed to your channel. Returns error 409 if the supplied RSS feed already exists.
        Note that the rss feed url should be URL-encoded.
        """
        channel_obj_dict = self.get_my_channel_obj_or_error(request)
        if channel_obj_dict[0] is None:
            return channel_obj_dict[1]

        channel_obj = channel_obj_dict[0]

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
        channel_obj_dict = self.get_my_channel_obj_or_error(request)
        if channel_obj_dict[0] is None:
            return channel_obj_dict[1]

        channel_obj = channel_obj_dict[0]

        if self.feed_url not in channel_obj.get_rss_feed_url_list():
            return ChannelModifyRssFeedEndpoint.return_404(request, message="this url is not added to your RSS feeds")

        channel_obj.remove_rss_feed(self.feed_url)
        return json.dumps({"removed": True})
