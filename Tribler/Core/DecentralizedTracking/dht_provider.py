import logging

from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id


class MainlineDHTProvider(object):
    """
    This class is a wrapper around the mainline DHT and is used for the hidden services as DHT provider.
    """

    def __init__(self, mainline_dht, bt_port):
        self.mainline_dht = mainline_dht
        self.bt_port = bt_port
        self.logger = logging.getLogger(self.__class__.__name__)

    def lookup(self, info_hash, cb):
        self.mainline_dht.get_peers(info_hash, Id(info_hash), cb)

    def announce(self, info_hash):
        def cb(info_hash, peers, source):
            self.logger.info("Announced %s to the DHT", info_hash.encode('hex'))

        self.mainline_dht.get_peers(info_hash, Id(info_hash), cb, bt_port=self.bt_port)
