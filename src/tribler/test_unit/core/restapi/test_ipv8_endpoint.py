from ipv8.test.base import TestBase

from tribler.core.restapi.ipv8_endpoint import IPv8RootEndpoint


class TestIPv8RootEndpoint(TestBase):
    """
    Tests for the IPv8RootEndpoint class.
    """

    def test_binding(self) -> None:
        """
        Test if all the IPv8 endpoint paths exist.
        """
        endpoint = IPv8RootEndpoint()
        endpoint.setup_routes()

        self.assertEqual("/api/ipv8", endpoint.path)
        self.assertIn("/asyncio", endpoint.endpoints)
        self.assertIn("/dht", endpoint.endpoints)
        self.assertIn("/identity", endpoint.endpoints)
        self.assertIn("/isolation", endpoint.endpoints)
        self.assertIn("/network", endpoint.endpoints)
        self.assertIn("/noblockdht", endpoint.endpoints)
        self.assertIn("/overlays", endpoint.endpoints)
        self.assertIn("/tunnel", endpoint.endpoints)
