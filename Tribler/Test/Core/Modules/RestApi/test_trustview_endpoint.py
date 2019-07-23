from __future__ import absolute_import

import random

from ipv8.attestation.trustchain.block import TrustChainBlock
from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.messaging.deprecated.encoding import encode
from ipv8.test.mocking.ipv8 import MockIPv8

from twisted.internet.defer import inlineCallbacks

import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout


class TestTrustViewEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestTrustViewEndpoint, self).setUp()

        self.mock_ipv8 = MockIPv8(u"low", TrustChainCommunity, working_directory=self.session.config.get_state_dir())
        self.session.lm.trustchain_community = self.mock_ipv8.overlay

        self.session.lm.bootstrap = MockObject()
        self.session.lm.bootstrap.download = MockObject()

        bootstrap_download_state = MockObject()
        bootstrap_download_state.get_total_transferred = lambda _: random.randint(0, 10000)
        bootstrap_download_state.get_progress = lambda: random.randint(10, 100)

        self.session.lm.bootstrap.download.get_state = lambda: bootstrap_download_state

    def setUpPreSession(self):
        super(TestTrustViewEndpoint, self).setUpPreSession()
        self.config.set_trustchain_enabled(True)

    @inlineCallbacks
    def tearDown(self):
        yield self.mock_ipv8.unload()
        yield super(TestTrustViewEndpoint, self).tearDown()

    @trial_timeout(10)
    def test_trustview_response(self):
        """
        Test whether the trust graph response is correctly returned.
        """

        def verify_response(response):
            response_json = json.twisted_loads(response)
            self.assertIsNotNone(response_json['graph_data'])
            self.assertEqual(response_json['num_tx'], 1)
            self.assertEqual(len(response_json['graph_data']['nodes']), 2)

        transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
        test_block = TrustChainBlock()
        test_block.type = b'tribler_bandwidth'
        test_block.transaction = transaction
        test_block._transaction = encode(transaction)
        test_block.public_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        test_block.hash = test_block.calculate_hash()
        self.session.lm.trustchain_community.persistence.add_block(test_block)

        self.should_check_equality = False
        return self.do_request(b'trustview', expected_code=200).addCallback(verify_response)
