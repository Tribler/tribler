from __future__ import absolute_import

import logging
import os
from binascii import hexlify, unhexlify

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo


class Bootstrap(object):
    """
    A class to create a bootstrap downloads for inital file aka bootstrap file.
    Bootstrap class will be initialized at the start of Tribler by downloading/seeding bootstrap file.
    """

    def __init__(self, boostrap_dir):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.dcfg = DownloadStartupConfig(is_bootstrap_download=True)
        self.dcfg.set_dest_dir(boostrap_dir)
        self.bootstrap_dir = boostrap_dir

        self.infohash = None
        self.download = None
        self.bootstrap_nodes = {}

    def start_initial_seeder(self, download_function, bootstrap_file):
        """
        Start as initial seeder for bootstrap_file
        :param download_function: function to download via tdef
        :return: download on bootstrap file
        """
        tdef = TorrentDef()
        tdef.add_content(bootstrap_file)
        tdef.set_piece_length(2 ** 16)
        tdef.save()
        self._logger.debug("Seeding bootstrap file %s", hexlify(tdef.infohash))
        self.download = download_function(tdef, download_startup_config=self.dcfg, hidden=True)
        self.infohash = tdef.get_infohash()

    def start_by_infohash(self, download_function, infohash):
        """
        Download bootstrap file from current seeders
        :param download_function: function to download via tdef
        :return: download on bootstrap file
        """
        self._logger.debug("Starting bootstrap downloading %s", infohash)
        tdef = TorrentDefNoMetainfo(unhexlify(infohash), name='bootstrap.block')
        self.download = download_function(tdef, download_startup_config=self.dcfg, hidden=True)
        self.infohash = infohash

    def get_bootstrap_peers(self, dht=None):
        if not self.download:
            return {}

        def on_dht_response(mid, nodes):
            for node in nodes:
                node_mid = hexlify(node.mid)
                # TODO: only persist peers with matching mid
                # if node_mid == mid:
                self.bootstrap_nodes[node_mid] = hexlify(node.public_key.key_to_bin())
            self.persist_nodes()

        def on_dht_error(error):
            self._logger.error("Failed to get DHT response:%s", error)

        for peer in self.download.get_peerlist():
            if peer['id'] not in self.bootstrap_nodes:
                mid = peer['id']
                self.bootstrap_nodes[mid] = None
                if dht:
                    dht.find_nodes(mid).addCallback(lambda nodes, mid=mid: on_dht_response(mid, nodes)).addErrback(on_dht_error)

        return self.bootstrap_nodes

    def persist_nodes(self):
        bootstrap_file = os.path.join(self.bootstrap_dir, "bootstrap.nodes")
        with open(bootstrap_file, "wb") as boot_file:
            for mid, public_key in self.bootstrap_nodes.items():
                if mid != "0000000000000000000000000000000000000000":
                    boot_file.write("%s:%s\n" % (mid, public_key))
