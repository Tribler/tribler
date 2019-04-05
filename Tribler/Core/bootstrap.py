from __future__ import absolute_import

import logging
from binascii import hexlify, unhexlify

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo


class Bootstrap(object):

    def __init__(self, boostrap_dir):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.dcfg = DownloadStartupConfig(is_bootstrap_download=True)
        self.dcfg.set_dest_dir(boostrap_dir)

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
        return download_function(tdef, download_startup_config=self.dcfg, hidden=True)

    def start_by_infohash(self, download_function, infohash):
        """
        Download bootstrap file from current seeders
        :param download_function: function to download via tdef
        :return: download on bootstrap file
        """
        self._logger.debug("Starting bootstrap downloading %s", infohash)
        tdef = TorrentDefNoMetainfo(unhexlify(infohash), name='bootstrap.block')
        return download_function(tdef, download_startup_config=self.dcfg, hidden=True)
