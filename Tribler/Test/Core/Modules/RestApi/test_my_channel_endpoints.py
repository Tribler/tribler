import json
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestMyChannelEndpoints(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(TestMyChannelEndpoints, self).setUp(autoload_discovery)
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def create_my_channel(self, name, description):
        """
        Utility method to create your channel
        """
        self.channel_db_handler._get_my_dispersy_cid = lambda: "myfakedispersyid"
        self.channel_db_handler.on_channel_from_dispersy('fakedispersyid', None, name, description)
        return self.channel_db_handler.getMyChannelId()

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
