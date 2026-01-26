from unittest.mock import Mock, call

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.restapi.shutdown_endpoint import ShutdownEndpoint


class TestShutdownEndpoint(TestBase):
    """
    Tests for the ShutdownEndpoint class.
    """

    async def test_shutdown(self) -> None:
        """
        Test if a call to the shutdown endpoint calls the shutdown event.
        """
        session = Mock()
        endpoint = ShutdownEndpoint(session)
        request = MockRequest("/api/shutdown", "PUT", {"restart": False})

        response = endpoint.shutdown_request(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["shutdown"])
        self.assertEqual(call(), session.shutdown_event.set.call_args)
        self.assertFalse(session.restart_requested)

    async def test_shutdown_forgotten_query(self) -> None:
        """
        Test if a call to the shutdown endpoint with a forgotten query argument still shuts down.
        """
        session = Mock()
        endpoint = ShutdownEndpoint(session)
        request = MockRequest("/api/shutdown", "PUT", {})

        response = endpoint.shutdown_request(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["shutdown"])
        self.assertEqual(call(), session.shutdown_event.set.call_args)
        self.assertFalse(session.restart_requested)

    async def test_shutdown_restart(self) -> None:
        """
        Test if a call to the shutdown endpoint with a restart request, sets the appropriate flag.
        """
        session = Mock()
        endpoint = ShutdownEndpoint(session)
        request = MockRequest("/api/shutdown", "PUT", {"restart": True})

        response = endpoint.shutdown_request(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["shutdown"])
        self.assertEqual(call(), session.shutdown_event.set.call_args)
        self.assertTrue(session.restart_requested)
