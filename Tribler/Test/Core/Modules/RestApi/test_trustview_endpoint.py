from __future__ import absolute_import

import random
from binascii import unhexlify

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
        root_key = self.session.lm.trustchain_community.my_peer.public_key.key_to_bin()
        friends = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9578",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b3",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf65",
        ]

        fofs = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9579",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b4",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf66",
        ]

        fofofs = [
            "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
            "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9580",
            "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
            "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b5",
            "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
            "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf67",
        ]

        def get_dummy_tx():
            return {
                'up': random.randint(1, 101),
                'down': random.randint(1, 101),
                'total_up': random.randint(1, 101),
                'total_down': random.randint(1, 101),
            }

        def verify_response(response, nodes, tx):
            response_json = json.twisted_loads(response)
            self.assertIsNotNone(response_json['graph'])
            self.assertEqual(response_json['num_tx'], tx)
            self.assertEqual(len(response_json['graph']['node']), nodes)

        test_block = TrustChainBlock()
        test_block.type = 'tribler_bandwidth'

        for seq, pub_key in enumerate(friends):
            test_block.transaction = get_dummy_tx()
            test_block._transaction = encode(test_block.transaction)

            test_block.sequence_number = seq
            test_block.public_key = root_key
            test_block.link_public_key = unhexlify(pub_key)

            test_block.hash = test_block.calculate_hash()
            self.session.lm.trustchain_community.persistence.add_block(test_block)

        for ind, friend in enumerate(friends):
            for ind2, fof in enumerate(fofs):
                test_block.transaction = get_dummy_tx()
                test_block._transaction = encode(test_block.transaction)

                test_block.sequence_number = ind + ind2
                test_block.public_key = unhexlify(friend)
                test_block.link_public_key = unhexlify(fof)

                test_block.hash = test_block.calculate_hash()
                self.session.lm.trustchain_community.persistence.add_block(test_block)

        for ind3, fof in enumerate(fofs):
            for ind4, fofof in enumerate(fofofs):
                test_block.transaction = get_dummy_tx()
                test_block._transaction = encode(test_block.transaction)

                test_block.sequence_number = ind3 + ind4
                test_block.public_key = unhexlify(fof)
                test_block.link_public_key = unhexlify(fofof)

                test_block.hash = test_block.calculate_hash()
                self.session.lm.trustchain_community.persistence.add_block(test_block)

        self.should_check_equality = False
        self.do_request(b'trustview?depth=1', expected_code=200).addCallback(lambda res: verify_response(res, 4, 3))
        self.do_request(b'trustview?depth=2', expected_code=200).addCallback(lambda res: verify_response(res, 7, 12))
        self.do_request(b'trustview?depth=3', expected_code=200).addCallback(lambda res: verify_response(res, 10, 21))
        return self.do_request(b'trustview?depth=4', expected_code=200).addCallback(
            lambda res: verify_response(res, 10, 21)
        )
