from __future__ import absolute_import

import random

from nose.tools import raises

from twisted.internet import reactor
from twisted.internet.protocol import Factory

from Tribler.Core.Utilities.network_utils import autodetect_socket_style, get_random_port
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.tools import trial_timeout


class TriblerCoreTestNetworkUtils(TriblerCoreTest):

    def test_get_random_port(self):
        random_port = get_random_port()
        self.assertIsInstance(random_port, int)
        self.assertTrue(random_port)

    @trial_timeout(5)
    def test_get_random_port_tcp(self):
        rand_port_num = random.randint(*self.get_bucket_range_port())
        listenport = reactor.listenTCP(rand_port_num, Factory())
        random_port = get_random_port(socket_type='tcp', min_port=rand_port_num, max_port=rand_port_num)
        self.assertGreaterEqual(random_port, rand_port_num+1)
        return listenport.stopListening()

    def test_get_random_port_udp(self):
        random_port = get_random_port(socket_type='udp')
        self.assertIsInstance(random_port, int)
        self.assertTrue(random_port)

    @raises(AssertionError)
    def test_get_random_port_invalid_type(self):
        get_random_port(socket_type="http")

    def test_autodetect_socket_style(self):
        style = autodetect_socket_style()
        self.assertTrue(style == 0 or autodetect_socket_style() == 1)
