import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks


class TestStatisticsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestStatisticsEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.mock_ipv8 = MockIPv8(u"low",
                                  TrustChainCommunity,
                                  working_directory=self.session.config.get_state_dir())
        self.mock_ipv8.overlays = [self.mock_ipv8.overlay]
        self.session.lm.ipv8 = self.mock_ipv8
        self.session.config.set_ipv8_enabled(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.session.lm.ipv8 = None
        yield self.mock_ipv8.unload()
        yield super(TestStatisticsEndpoint, self).tearDown(annotate=annotate)

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
