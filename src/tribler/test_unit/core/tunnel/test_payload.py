from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.tunnel.payload import HTTPRequestPayload, HTTPResponsePayload


class TestHTTPPayloads(TestBase):
    """
    Tests for the various payloads of the TriblerTunnelCommunity.
    """

    def test_http_request_payload(self) -> None:
        """
        Test if HTTPRequestPayload initializes correctly.
        """
        hrqp = HTTPRequestPayload(42, 7, ("1.2.3.4", 5), b"test")

        self.assertEqual(28, hrqp.msg_id)
        self.assertEqual(42, hrqp.circuit_id)
        self.assertEqual(7, hrqp.identifier)
        self.assertEqual(("1.2.3.4", 5), hrqp.target)
        self.assertEqual(b"test", hrqp.request)

    def test_http_response_payload(self) -> None:
        """
        Test if HTTPResponsePayload initializes correctly.
        """
        hrsp = HTTPResponsePayload(42, 7, 3, 5, b"test")

        self.assertEqual(29, hrsp.msg_id)
        self.assertEqual(42, hrsp.circuit_id)
        self.assertEqual(7, hrsp.identifier)
        self.assertEqual(3, hrsp.part)
        self.assertEqual(5, hrsp.total)
        self.assertEqual(b"test", hrsp.response)
