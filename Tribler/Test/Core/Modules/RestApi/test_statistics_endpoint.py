
from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.mocking.ipv8 import MockIPv8

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import timeout


class TestStatisticsEndpoint(AbstractApiTest):

    async def setUp(self):
        await super(TestStatisticsEndpoint, self).setUp()

        self.mock_ipv8 = MockIPv8(u"low",
                                  TrustChainCommunity,
                                  working_directory=self.session.config.get_state_dir())
        self.mock_ipv8.overlays = [self.mock_ipv8.overlay]
        self.mock_ipv8.endpoint.bytes_up = 100
        self.mock_ipv8.endpoint.bytes_down = 20
        self.session.ipv8 = self.mock_ipv8
        self.session.config.set_ipv8_enabled(True)
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.session.mds = MetadataStore(self.session_base_dir / 'test.db', self.session_base_dir,
                                            my_key)

    async def tearDown(self):
        self.session.mds.shutdown()
        self.session.ipv8 = None
        await self.mock_ipv8.unload()
        await super(TestStatisticsEndpoint, self).tearDown()

    @timeout(10)
    async def test_get_tribler_statistics(self):
        """
        Testing whether the API returns a correct Tribler statistics dictionary when requested
        """
        json_data = await self.do_request('statistics/tribler', expected_code=200)
        self.assertIn("tribler_statistics", json_data)

    @timeout(10)
    async def test_get_ipv8_statistics(self):
        """
        Testing whether the API returns a correct Dispersy statistics dictionary when requested
        """
        json_data = await self.do_request('statistics/ipv8', expected_code=200)
        self.assertTrue(json_data["ipv8_statistics"])

    @timeout(10)
    async def test_get_ipv8_statistics_unavailable(self):
        """
        Testing whether the API returns error 500 if IPv8 is not available
        """
        self.session.ipv8 = None
        json_data = await self.do_request('statistics/ipv8', expected_code=200)
        self.assertFalse(json_data["ipv8_statistics"])
