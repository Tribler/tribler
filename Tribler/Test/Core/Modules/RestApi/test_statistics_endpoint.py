from nose.twistedtools import deferred
from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestStatisticsEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestStatisticsEndpoint, self).setUp()

        self.mock_ipv8 = MockIPv8(u"low",
                                  TrustChainCommunity,
                                  working_directory=self.session.config.get_state_dir())
        self.mock_ipv8.overlays = [self.mock_ipv8.overlay]
        self.mock_ipv8.endpoint.bytes_up = 100
        self.mock_ipv8.endpoint.bytes_down = 20
        self.session.lm.ipv8 = self.mock_ipv8
        self.session.config.set_ipv8_enabled(True)

    @inlineCallbacks
    def tearDown(self):
        self.session.lm.ipv8 = None
        yield self.mock_ipv8.unload()
        yield super(TestStatisticsEndpoint, self).tearDown()

    def setUpPreSession(self):
        super(TestStatisticsEndpoint, self).setUpPreSession()
        self.config.set_dispersy_enabled(True)
        self.config.set_torrent_collecting_enabled(True)

    @deferred(timeout=10)
    def test_get_tribler_statistics(self):
        """
        Testing whether the API returns a correct Tribler statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["tribler_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/tribler', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_dispersy_statistics(self):
        """
        Testing whether the API returns a correct Dispersy statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["dispersy_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/dispersy', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_ipv8_statistics(self):
        """
        Testing whether the API returns a correct Dispersy statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["ipv8_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/ipv8', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_ipv8_statistics_unavailable(self):
        """
        Testing whether the API returns error 500 if IPv8 is not available
        """
        self.session.config.set_ipv8_enabled(False)

        def verify_dict(data):
            self.assertFalse(json.loads(data)["ipv8_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/ipv8', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_community_statistics(self):
        """
        Testing whether the API returns a correct community statistics dictionary when requested
        """
        def verify_dict(data):
            json_data = json.loads(data)
            self.assertTrue(json_data["dispersy_community_statistics"])
            self.assertTrue(json_data["ipv8_overlay_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/communities', expected_code=200).addCallback(verify_dict)
