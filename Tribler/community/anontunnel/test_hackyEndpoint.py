import threading
from unittest import TestCase
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.endpoint import DispersyBypassEndpoint

__author__ = 'chris'


class TestDispersyBypassEndpoint(TestCase):
    def on_bypass_message(self, sock_addr, payload):
        self.bypass_message = (sock_addr, payload)

    def setUp(self):
        self.succeed = False

        done_flag = threading.Event()
        raw_server = RawServer(done_flag, 10, 5);

        self.endpoint = DispersyBypassEndpoint(raw_server, 0)

    def test_data_came_in(self):
        prefix = ('f' * 23 + 'e').decode("HEX")
        self.endpoint.listen_to(prefix, self.on_bypass_message)

        packet = (
            ("127.0.0.1", 100),
            prefix + "Hello world!"
        )

        self.endpoint.data_came_in([packet])

        self.assertEqual(self.bypass_message, packet)