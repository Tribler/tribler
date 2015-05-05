# Written by Niels Zeilemaker
# see LICENSE.txt for license information

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Utilities.Instance2Instance import Instance2InstanceServer, \
    Instance2InstanceClient
from Tribler.Core.Utilities.network_utils import get_random_port
from threading import Event

class TestThreadPool(AbstractServer):

    def test_client_server(self):
        got_callback = Event()
        line_callback = [None]
        def readline_callback(socket, line):
            line_callback[0] = line
            got_callback.set()

        port = get_random_port()
        self.i2i_server = Instance2InstanceServer(port, readline_callback)
        self.i2i_cleint = Instance2InstanceClient(port, 'START', 'XYZ')

        self.assertTrue(got_callback.wait(5), "did not received callback")
        self.assertEqual('START XYZ', line_callback[0], "lines did not match")
