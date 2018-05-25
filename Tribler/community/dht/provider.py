import logging
import struct
import socket


class DHTCommunityProvider(object):
    """
    This class is a wrapper around the DHTCommunity and is used for the hidden services as DHT provider.
    """

    def __init__(self, dhtcommunity, bt_port):
        self.dhtcommunity = dhtcommunity
        self.bt_port = bt_port
        self.logger = logging.getLogger(self.__class__.__name__)

    def lookup(self, info_hash, cb):
        def callback(values):
            addresses = []
            for value in values:
                try:
                    ip, port = struct.unpack('!4sH', value)
                    address = (socket.inet_ntoa(ip), port)
                    addresses.append(address)
                except (struct.error, socket.error):
                    self.logger.info("Failed to decode value '%s' from DHTCommunity", value)
            return info_hash, addresses, None
        self.dhtcommunity.find_values(info_hash).addCallback(callback).addCallbacks(cb, lambda _: None)

    def announce(self, info_hash):
        def callback(_):
            self.logger.info("Announced %s to the DHTCommunity", info_hash.encode('hex'))
        def errback(_):
            self.logger.info("Failed to announce %s to the DHTCommunity", info_hash.encode('hex'))
        value = socket.inet_aton(self.dhtcommunity.my_estimated_lan[0]) + struct.pack("!H", self.bt_port)
        self.dhtcommunity.store_value(info_hash, value).addCallbacks(callback, errback)
