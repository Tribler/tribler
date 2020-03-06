import logging
import os
from binascii import unhexlify

from ipv8.dht import DHTError
from ipv8.taskmanager import TaskManager

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.torrentdef import TorrentDefNoMetainfo
from tribler_core.utilities.unicode import hexlify


class Bootstrap(TaskManager):
    """
    A class to create a bootstrap downloads for inital file aka bootstrap file.
    Bootstrap class will be initialized at the start of Tribler by downloading/seeding bootstrap file.
    """

    def __init__(self, config_dir, dht=None):
        super(Bootstrap, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.dcfg = DownloadConfig(state_dir=config_dir)
        self.dcfg.set_bootstrap_download(True)
        self.bootstrap_dir = config_dir / 'bootstrap'
        if not self.bootstrap_dir.exists():
            os.mkdir(self.bootstrap_dir)
        self.dcfg.set_dest_dir(self.bootstrap_dir)
        self.dcfg.set_safe_seeding(True)
        self.bootstrap_file = self.bootstrap_dir / "bootstrap.blocks"
        self.dht = dht

        self.bootstrap_finished = False
        self.infohash = None
        self.download = None
        self.bootstrap_nodes = {}

        self.register_task('fetch_bootstrap_peers', self.fetch_bootstrap_peers, interval=5)

    def start_by_infohash(self, download_function, infohash):
        """
        Download bootstrap file from current seeders
        :param download_function: function to download via tdef
        :return: download on bootstrap file
        """
        self._logger.debug("Starting bootstrap downloading %s", infohash)
        tdef = TorrentDefNoMetainfo(unhexlify(infohash), name='bootstrap.blocks')
        self.download = download_function(tdef=tdef, config=self.dcfg, hidden=True)
        self.infohash = infohash

    async def fetch_bootstrap_peers(self):
        if not self.download:
            return {}

        for peer in self.download.get_peerlist():
            mid = peer['id']
            if (mid not in self.bootstrap_nodes or not self.bootstrap_nodes[mid]) and mid != "0" * 40:
                if self.dht:
                    try:
                        nodes = await self.dht.connect_peer(bytes(unhexlify(mid)))
                    except DHTError as e:
                        self._logger.error("Failed to get DHT response:%s", e)
                        continue

                    if not nodes:
                        return
                    for node in nodes:
                        self.bootstrap_nodes[hexlify(node.mid)] = hexlify(node.public_key.key_to_bin())
        return self.bootstrap_nodes

    async def shutdown(self):
        await self.shutdown_task_manager()
