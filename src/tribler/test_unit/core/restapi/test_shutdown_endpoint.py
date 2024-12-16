from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.restapi.shutdown_endpoint import ShutdownEndpoint


class TestShutdownEndpoint(TestBase):
    """
    Tests for the ShutdownEndpoint class.
    """

    async def test_shutdown(self) -> None:
        """
        Test if a call to the shutdown endpoint calls the shutdown callback.
        """
        value = [2, 1]
        endpoint = ShutdownEndpoint(value.reverse)
        request = MockRequest("/api/shutdown", "PUT")

        response = endpoint.shutdown_request(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["shutdown"])
        self.assertEqual([1, 2], value)
