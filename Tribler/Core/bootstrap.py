from __future__ import absolute_import

import logging
import os
from binascii import hexlify, unhexlify

from six import b

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo


class Bootstrap(object):
    """
    A class to create a bootstrap downloads for inital file aka bootstrap file.
    Bootstrap class will be initialized at the start of Tribler by downloading/seeding bootstrap file.
    """

    def __init__(self, config_dir, dht=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.dcfg = DownloadConfig(state_dir=config_dir)
        self.dcfg.set_bootstrap_download(True)
        self.bootstrap_dir = os.path.join(config_dir, 'bootstrap')
        if not os.path.exists(self.bootstrap_dir):
            os.mkdir(self.bootstrap_dir)
        self.dcfg.set_dest_dir(self.bootstrap_dir)
        self.bootstrap_file = os.path.join(self.bootstrap_dir, "bootstrap.blocks")
        self.nodes_file = os.path.join(self.bootstrap_dir, "bootstrap.nodes")
        self.dht = dht

        self.bootstrap_finished = False
        self.infohash = None
        self.download = None
        self.bootstrap_nodes = {}
        self.load_bootstrap_nodes()

    def start_initial_seeder(self, download_function, bootstrap_file, system_infohash):
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
        self.download = download_function(tdef, download_config=self.dcfg, hidden=True)
        self.infohash = tdef.get_infohash()
        if hexlify(self.infohash) != system_infohash:
            self._logger.error(
                "Infohash is not consistent with a system infohash %s != %s", hexlify(self.infohash),
                system_infohash)

    def start_by_infohash(self, download_function, infohash):
        """
        Download bootstrap file from current seeders
        :param download_function: function to download via tdef
        :return: download on bootstrap file
        """
        self._logger.debug("Starting bootstrap downloading %s", infohash)
        tdef = TorrentDefNoMetainfo(unhexlify(infohash), name='bootstrap.blocks')
        self.download = download_function(tdef, download_config=self.dcfg, hidden=True)
        self.infohash = infohash

    def fetch_bootstrap_peers(self):
        if not self.download:
            return {}

        def on_success(nodes):
            if not nodes:
                return
            for node in nodes:
                self.bootstrap_nodes[hexlify(node.mid)] = hexlify(node.public_key.key_to_bin())
            self.persist_nodes()

        def on_failure(failure):
            self._logger.error("Failed to get DHT response:%s", failure.value.message)

        for peer in self.download.get_peerlist():
            mid = peer['id']
            if (mid not in self.bootstrap_nodes or not self.bootstrap_nodes[mid]) \
                    and mid != "0000000000000000000000000000000000000000":
                if self.dht:
                    self.dht.connect_peer(bytes(unhexlify(mid))).addCallbacks(on_success, on_failure)

        return self.bootstrap_nodes

    def persist_nodes(self):
        with open(self.nodes_file, "wb") as boot_file:
            for mid, public_key in self.bootstrap_nodes.items():
                if mid != "0000000000000000000000000000000000000000" and public_key:
                    boot_file.write(b"%s:%s\n" % (mid, public_key))

    def load_bootstrap_nodes(self):
        if not os.path.exists(self.nodes_file):
            return
        with open(self.nodes_file, "r") as boot_file:
            for line in boot_file:
                if line and ":" in line:
                    mid, pub_key = line.rstrip().split(":")
                    self.bootstrap_nodes[b(mid)] = b(pub_key)
