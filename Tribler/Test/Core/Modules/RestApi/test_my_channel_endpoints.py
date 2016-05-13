import json

from Tribler.Core.Modules.channel.channel import ChannelObject
from Tribler.Core.Modules.channel.channel_manager import ChannelManager
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class ChannelCommunityMock(object):

    def __init__(self, channel_id):
        self.name = "Channel name"
        self.cid = 'a' * 20
        self.channel_id = channel_id

    def get_channel_name(self):
        return self.name

    def get_channel_id(self):
        return self.channel_id


class AbstractTestMyChannelEndpoints(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(AbstractTestMyChannelEndpoints, self).setUp(autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def create_my_channel(self, name, description):
        """
        Utility method to create your channel
        """
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        self.channel_db_handler.on_channel_from_dispersy('fakedispersyid', None, name, description)
        return self.channel_db_handler.getMyChannelId()

    def create_fake_channel(self, channel_name, channel_description):
        # Use a fake ChannelCommunity object (we don't actually want to create a Dispersy community)
        my_channel_id = self.create_my_channel(channel_name, channel_description)
        self.session.lm.channel_manager = ChannelManager(self.session)

        channel_obj = ChannelObject(self.session, ChannelCommunityMock(my_channel_id))
        self.session.lm.channel_manager._channel_list.append(channel_obj)
        return my_channel_id


class TestMyChannelEndpoints(AbstractTestMyChannelEndpoints):

    @deferred(timeout=10)
    def test_my_channel_unknown_endpoint(self):
        """
        Testing whether the API returns an error if an unknown endpoint is queried
        """
        self.should_check_equality = False
        return self.do_request('mychannel/thisendpointdoesnotexist123', expected_code=404)

    def insert_torrents_into_my_channel(self, torrent_list):
        self.channel_db_handler.on_torrents_from_dispersy(torrent_list)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created
        """
        return self.do_request('mychannel/overview', expected_code=404)

    @deferred(timeout=10)
    def test_my_channel_overview_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a channel overview is requested
        """
        channel_json = {u'overview': {u'name': u'testname', u'description': u'testdescription',
                                      u'identifier': 'fakedispersyid'.encode('hex')}}
        self.create_my_channel(channel_json[u'overview'][u'name'], channel_json[u'overview'][u'description'])

        return self.do_request('mychannel/overview', expected_code=200, expected_json=channel_json)

    @deferred(timeout=10)
    def test_my_channel_torrents_endpoint_no_my_channel(self):
        """
        Testing whether the API returns response code 404 if no channel has been created when fetching torrents
        """
        return self.do_request('mychannel/torrents', expected_code=404)

    def verify_torrents_json(self, body):
        torrents_dict = json.loads(body)
        self.assertTrue(torrents_dict["torrents"])
        self.assertEqual(len(torrents_dict["torrents"]), 1)

    @deferred(timeout=10)
    def test_torrents_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a torrents from a channel are fetched
        """
        self.should_check_equality = False
        my_channel_id = self.create_my_channel("my channel", "this is a short description")
        torrent_list = [[my_channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso", [], []]]
        self.insert_torrents_into_my_channel(torrent_list)

        return self.do_request('mychannel/torrents', expected_code=200).addCallback(self.verify_torrents_json)

    @deferred(timeout=10)
    def test_rss_feeds_endpoint_no_my_channel(self):
        """
        Testing whether the API returns the right JSON data if no channel has been created when fetching rss feeds
        """
        self.session.lm.channel_manager = ChannelManager(self.session)
        return self.do_request('mychannel/rssfeeds', expected_code=404)


class TestMyChannelRssEndpoints(AbstractTestMyChannelEndpoints):

    @deferred(timeout=10)
    def test_rss_feeds_endpoint_with_channel(self):
        """
        Testing whether the API returns the right JSON data if a rss feeds from a channel are fetched
        """
        expected_json = {u'rssfeeds': [{u'url': u'http://test1.com/feed.xml'}, {u'url': u'http://test2.com/feed.xml'}]}
        self.create_fake_channel("my channel", "this is a short description")
        channel_obj = self.session.lm.channel_manager.get_channel("Channel name")
        for rss_item in expected_json[u'rssfeeds']:
            channel_obj.create_rss_feed(rss_item[u'url'])

        return self.do_request('mychannel/rssfeeds', expected_code=200, expected_json=expected_json)

    @deferred(timeout=10)
    def test_add_rss_feed_no_my_channel(self):
        """
        Testing whether the API returns a 404 if no channel has been created when adding a rss feed
        """
        self.session.lm.channel_manager = ChannelManager(self.session)
        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml',
                               expected_code=404, request_type='PUT')

    @deferred(timeout=10)
    def test_add_rss_feed_conflict(self):
        """
        Testing whether the API returns error 409 if a channel the rss feed already exists
        """
        expected_json = {"error": "this rss feed already exists"}
        my_channel_id = self.create_fake_channel("my channel", "this is a short description")
        channel_obj = self.session.lm.channel_manager.get_my_channel(my_channel_id)
        channel_obj.create_rss_feed("http://rssfeed.com/rss.xml")

        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml', expected_code=409,
                               expected_json=expected_json, request_type='PUT')

    @deferred(timeout=10)
    def test_add_rss_feed_with_channel(self):
        """
        Testing whether the API returns a 200 if a channel has been created and when adding a rss feed
        """
        def verify_rss_added(_):
            channel_obj = self.session.lm.channel_manager.get_my_channel(my_channel_id)
            self.assertEqual(channel_obj.get_rss_feed_url_list(), ["http://rssfeed.com/rss.xml"])

        expected_json = {"added": True}
        my_channel_id = self.create_fake_channel("my channel", "this is a short description")
        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml', expected_code=200,
                               expected_json=expected_json, request_type='PUT')\
            .addCallback(verify_rss_added)

    @deferred(timeout=10)
    def test_remove_rss_feed_no_channel(self):
        """
        Testing whether the API returns a 404 if no channel has been created when adding a rss feed
        """
        self.session.lm.channel_manager = ChannelManager(self.session)
        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml',
                               expected_code=404, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_rss_feed_invalid_url(self):
        """
        Testing whether the API returns a 404 and error if the url parameter does not exist in the existing feeds
        """
        expected_json = {"error": "this url is not added to your RSS feeds"}
        self.create_fake_channel("my channel", "this is a short description")
        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml', expected_code=404,
                               expected_json=expected_json, request_type='DELETE')

    @deferred(timeout=10)
    def test_remove_rss_feed_with_channel(self):
        """
        Testing whether the API returns a 200 if a channel has been created and when removing a rss feed
        """
        def verify_rss_removed(_):
            channel_obj = self.session.lm.channel_manager.get_my_channel(my_channel_id)
            self.assertEqual(channel_obj.get_rss_feed_url_list(), [])

        expected_json = {"removed": True}
        my_channel_id = self.create_fake_channel("my channel", "this is a short description")
        channel_obj = self.session.lm.channel_manager.get_my_channel(my_channel_id)
        channel_obj.create_rss_feed("http://rssfeed.com/rss.xml")

        return self.do_request('mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml', expected_code=200,
                               expected_json=expected_json, request_type='DELETE').addCallback(verify_rss_removed)
