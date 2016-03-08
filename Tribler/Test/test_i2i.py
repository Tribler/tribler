# Written by Niels Zeilemaker
# see LICENSE.txt for license information
import time
from twisted.internet.defer import Deferred
from Tribler.Core.Utilities.twisted_thread import deferred

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Utilities.Instance2Instance import Instance2InstanceServer, \
    Instance2InstanceClient
from Tribler.Core.Utilities.network_utils import get_random_port

class TestThreadPool(AbstractServer):

    @deferred(timeout=5)
    def test_client_server(self):
        port = get_random_port()
        i2i_server = Instance2InstanceServer(port)
        d = Deferred()

        def on_message_received(socket, line):
            return i2i_server.stop().addCallback(on_test_finished, line).chainDeferred(d)

        def on_test_finished(_, line):
            self.assertEqual('START XYZ', line, "lines did not match")

        def on_server_connected(_):
            Instance2InstanceClient(port, 'START', 'XYZ')

        i2i_server.start(on_message_received).addCallback(on_server_connected)

        return d
