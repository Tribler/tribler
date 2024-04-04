from ipv8.test.base import TestBase

from tribler.core.restapi.shutdown_endpoint import ShutdownEndpoint
from tribler.test_unit.base_restapi import MockRequest, response_to_json


class ShutdownRequest(MockRequest):
    """
    A MockRequest that mimics ShutdownRequests.
    """

    def __init__(self) -> None:
        """
        Create a new ShutdownRequest.
        """
        super().__init__({}, "PUT", "/shutdown")


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

        response = endpoint.shutdown_request(ShutdownRequest())
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["shutdown"])
        self.assertEqual([1, 2], value)
