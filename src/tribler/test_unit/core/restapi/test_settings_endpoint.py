from unittest.mock import Mock, call

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.restapi.settings_endpoint import SettingsEndpoint
from tribler.test_unit.mocks import MockTriblerConfigManager


class UpdateSettingsRequest(MockRequest):
    """
    A MockRequest that mimics UpdateSettingsRequests.
    """

    def __init__(self, raw_json_content: bytes) -> None:
        """
        Create a new UpdateSettingsRequest.
        """
        super().__init__("/api/settings", "POST")
        self.raw_json_content = raw_json_content

    async def read(self) -> bytes:
        """
        Get the json contents of this request.
        """
        return self.raw_json_content


class TestSettingsEndpoint(TestBase):
    """
    Tests for the SettingsEndpoint class.
    """

    async def test_get_settings(self) -> None:
        """
        Test if settings can be retrieved.
        """
        config = MockTriblerConfigManager()
        config.set("api/http_port", 1337)
        endpoint = SettingsEndpoint(config)
        request = MockRequest("/api/settings")

        response = await endpoint.get_settings(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(1337, response_body_json["settings"]["api"]["http_port"])

    async def test_update_settings(self) -> None:
        """
        Test if settings can be changed.
        """
        config = MockTriblerConfigManager()
        endpoint = SettingsEndpoint(config)
        request = UpdateSettingsRequest(b'{"api":{"http_port":1337}}')

        response = await endpoint.update_settings(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["modified"])
        self.assertEqual(1337, config.get("api/http_port"))

    async def test_update_settings_download_manager(self) -> None:
        """
        Test if a registered download manager is notified of a settings update.
        """
        config = MockTriblerConfigManager()
        endpoint = SettingsEndpoint(config)
        endpoint.download_manager = Mock(update_max_rates_from_config=Mock(return_value=None))
        request = UpdateSettingsRequest(b'{"api":{"http_port":1337}}')

        response = await endpoint.update_settings(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["modified"])
        self.assertEqual(1337, config.get("api/http_port"))
        self.assertEqual(call(), endpoint.download_manager.update_max_rates_from_config.call_args)
