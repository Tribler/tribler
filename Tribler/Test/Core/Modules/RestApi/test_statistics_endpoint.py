import os

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.tools import trial_timeout
from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto
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
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.session.lm.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir, my_key)

    @inlineCallbacks
    def tearDown(self):
        self.session.lm.mds.shutdown()
        self.session.lm.ipv8 = None
        yield self.mock_ipv8.unload()
        yield super(TestStatisticsEndpoint, self).tearDown()

    @trial_timeout(10)
    def test_get_tribler_statistics(self):
        """
        Testing whether the API returns a correct Tribler statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertIn("tribler_statistics", json.loads(data))

        self.should_check_equality = False
        return self.do_request('statistics/tribler', expected_code=200).addCallback(verify_dict)

    @trial_timeout(10)
    def test_get_ipv8_statistics(self):
        """
        Testing whether the API returns a correct Dispersy statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["ipv8_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/ipv8', expected_code=200).addCallback(verify_dict)

    @trial_timeout(10)
    def test_get_ipv8_statistics_unavailable(self):
        """
        Testing whether the API returns error 500 if IPv8 is not available
        """
        self.session.config.set_ipv8_enabled(False)

        def verify_dict(data):
            self.assertFalse(json.loads(data)["ipv8_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/ipv8', expected_code=200).addCallback(verify_dict)
