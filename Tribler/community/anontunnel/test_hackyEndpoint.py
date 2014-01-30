import threading
from unittest import TestCase
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.endpoint import HackyEndpoint

__author__ = 'chris'


class TestHackyEndpoint(TestCase):
    def on_bypass_message(self, sock_addr, payload):
        self.bypass_message = (sock_addr, payload)

    def setUp(self):
        self.succeed = False

        done_flag = threading.Event()
        raw_server = RawServer(done_flag, 10, 5);

        self.endpoint = HackyEndpoint(raw_server, 0)

    def test_data_came_in(self):
        prefix = ('f' * 23 + 'e').decode("HEX")
        self.endpoint.bypass_prefix = prefix
        self.endpoint.bypass_community = self

        packet = (
            ("127.0.0.1", 100),
            prefix + "Hello world!"
        )

        self.endpoint.data_came_in([packet])

        self.assertEqual(self.bypass_message, packet)