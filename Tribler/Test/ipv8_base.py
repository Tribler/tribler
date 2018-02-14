import os
import sys
import threading
import time
import traceback

import twisted
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.trial import unittest

twisted.internet.base.DelayedCall.debug = True

from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread
from Tribler.Test.mocking.endpoint import internet
from Tribler.Test.mocking.ipv8 import MockIPv8


class TestBase(unittest.TestCase):

    __testing__ = True
    __lockup_timestamp__ = 0

    # The time after which the whole test suite is os.exited
    MAX_TEST_TIME = 100000

    def __init__(self, methodName='runTest'):
        super(TestBase, self).__init__(methodName)
        self.nodes = []
        self.overlay_class = object
        internet.clear()

    def initialize(self, overlay_class, node_count, *args, **kwargs):
        self.overlay_class = overlay_class
        self.nodes = [self.create_node(*args, **kwargs) for _ in range(node_count)]

        # Add nodes to each other
        for node in self.nodes:
            for other in self.nodes:
                if other == node:
                    continue
                private_peer = other.my_peer
                public_peer = Peer(private_peer.public_key, private_peer.address)
                node.network.add_verified_peer(public_peer)
                node.network.discover_services(public_peer, overlay_class.master_peer.mid)

    def setUp(self):
        super(TestBase, self).setUp()
        self.__lockup_timestamp__ = time.time()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self):
        yield super(TestBase, self).tearDown()
        for node in self.nodes:
            yield node.unload()
        internet.clear()

    @classmethod
    def setUpClass(cls):
        cls.__lockup_timestamp__ = time.time()
        def check_twisted():
            while time.time() - cls.__lockup_timestamp__ < cls.MAX_TEST_TIME:
                time.sleep(2)
                # If the test class completed normally, exit
                if not cls.__testing__:
                    return
            # If we made it here, there is a serious issue which we cannot recover from.
            # Most likely the Twisted threadpool got into a deadlock while shutting down.
            print >> sys.stderr, "The test-suite locked up! Force quitting! Thread dump:"
            for tid, stack in sys._current_frames().items():
                if tid != threading.currentThread().ident:
                    print >> sys.stderr, "THREAD#%d" % tid
                    for line in traceback.format_list(traceback.extract_stack(stack)):
                        print >> sys.stderr, "|", line[:-1].replace('\n', '\n|   ')
            os._exit(1)
        t = threading.Thread(target=check_twisted)
        t.daemon = True
        t.start()

    @classmethod
    def tearDownClass(cls):
        cls.__testing__ = False

    def create_node(self, *args, **kwargs):
        return MockIPv8(u"low", self.overlay_class, *args, **kwargs)

    def add_node_to_experiment(self, node):
        """
        Add a new node to this experiment (use `create_node()`).
        """
        for other in self.nodes:
            private_peer = other.my_peer
            public_peer = Peer(private_peer.public_key, private_peer.address)
            node.network.add_verified_peer(public_peer)
            node.network.discover_services(public_peer, node.overlay.master_peer.mid)
        self.nodes.append(node)

    @inlineCallbacks
    def deliver_messages(self, timeout=.1):
        """
        Allow peers to communicate.
        The strategy is as follows:
         1. Measure the amount of working threads in the threadpool
         2. After 10 milliseconds, check if we are down to 0 twice in a row
         3. If not, go back to handling calls (step 2) or return, if the timeout has been reached
        :param timeout: the maximum time to wait for messages to be delivered
        """
        rtime = 0
        probable_exit = False
        while rtime < timeout:
            yield self.sleep(.01)
            rtime += .01
            if len(reactor.getThreadPool().working) == 0:
                if probable_exit:
                    break
                probable_exit = True
            else:
                probable_exit = False

    @inlineCallbacks
    def sleep(self, time=.05):
        yield deferLater(reactor, time, lambda: None)

    @inlineCallbacks
    def introduce_nodes(self):
        for node in self.nodes:
            node.discovery.take_step()
        yield self.sleep()
