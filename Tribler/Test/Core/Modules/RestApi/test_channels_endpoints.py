import json
import time
from Tribler.Core.Modules.restapi.channels_endpoint import VOTE_SUBSCRIBE, VOTE_UNSUBSCRIBE

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_VOTECAST
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestChannelTorrentsEndpoint(AbstractTestChannelsEndpoint):

    @deferred(timeout=10)
    def test_get_torrents_in_channel_invalid_cid(self):
        """
        Testing whether the API returns error 404 if a non-existent channel is queried for torrents
        """
        self.should_check_equality = False
        return self.do_request('channels/discovered/abcd/torrents', expected_code=404)

    @deferred(timeout=10)
    def test_get_torrents_in_channel(self):
        """
        Testing whether the API returns inserted torrents when fetching discovered channels
        """
        def verify_torrents(torrents):
            torrents_json = json.loads(torrents)
            self.assertEqual(len(torrents_json['torrents']), 1)
            self.assertEqual(torrents_json['torrents'][0]['infohash'], 'a' * 40)

        self.should_check_equality = False
        channel_id = self.insert_channel_in_db('rand', 42, 'Test channel', 'Test description')

        torrent_list = [[channel_id, 1, 1, ('a' * 40).decode('hex'), 1460000000, "ubuntu-torrent.iso",
                         [['file1.txt', 42]], []]]
        self.insert_torrents_into_channel(torrent_list)

        return self.do_request('channels/discovered/%s/torrents' % 'rand'.encode('hex'), expected_code=200)\
            .addCallback(verify_torrents)
