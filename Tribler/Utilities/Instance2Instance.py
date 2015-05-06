# Written by Niels Zeilemaker
# see LICENSE.txt for license information
""" Communication layer between other instance or Web plugin e.g. for starting Downloads. """

# Protocol V1: Tribler 4.5.0:
# - [4 byte length of cmd][cmd]
# Protocol V2: SwarmPlugin
# - [cmd]\r\n
#

import logging
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
import socket

class I2I(LineReceiver):

    def lineReceived(self, line):
        self.factory.callback(self, line)

    def close(self):
        self.transport.loseConnection()

class I2IFactory(Factory):
    protocol = I2I

    def __init__(self, callback):
        self.callback = callback

class Instance2InstanceServer():

    def __init__(self, i2iport, callback):
        endpoint = TCP4ServerEndpoint(reactor, i2iport, interface="127.0.0.1")
        endpoint.listen(I2IFactory(callback))

class Instance2InstanceClient(object):

    def __init__(self, port, cmd, param):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', port))
        msg = cmd + ' ' + param + '\r\n'
        s.send(msg)
        s.close()