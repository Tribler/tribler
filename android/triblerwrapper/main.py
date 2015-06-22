# coding: utf-8

# Written by Wendo Sabée
# The main class that loads the Tribler session, all managers and sets up a XML-RPC server

# Version number that Kivy's Buildozer requires:
__version__ = "0.0.1"

USE_TWISTED_XMLRPC = False

import threading
import time
import sys
import os

# SETUP ENVIRONMENT, DO THIS FIRST
from Environment import init_environment
init_environment()

# Init logger
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

arg = os.getenv('PYTHON_SERVICE_ARGUMENT')

# Local files
from TriblerSession import TriblerSession
from SettingsManager import SettingsManager
from ChannelManager import ChannelManager
from TorrentManager import TorrentManager
from DownloadManager import DownloadManager
if USE_TWISTED_XMLRPC:
    from XMLRpc_twisted import XMLRPCServer
else:
    from XMLRpc import XMLRPCServer


class TSAP():
    tribler = None
    xmlrpc = None
    dm = None
    tm = None
    cm = None

    def __init__(self):
        pass

    def stop(self):
        self.tribler.stop_session()
        xmlrpc = None

    def run(self):
        """
        This sets up a Tribler session, loads the managers and the XML-RPC server.
        :return: Nothing.
        """

        _logger.error("Loading XMLRPCServer")
        self.xmlrpc = XMLRPCServer(iface="0.0.0.0", port=8000)

        _logger.error("Loading TriblerSessionService")
        self.tribler = TriblerSession(self.xmlrpc)
        self.tribler.start_session()

        # Wait for dispersy to initialize
        while not self.tribler.is_running():
            time.sleep(0.1)

        # Disable ChannelManager
        #_logger.error("Loading ChannelManager")
        #self.cm = ChannelManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading TorrentManager")
        self.tm = TorrentManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading DownloadManager")
        self.dm = DownloadManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Loading ConfigurationManager")
        # Load this last because it sets settings in other managers
        self.sm = SettingsManager.getInstance(self.tribler.get_session(), self.xmlrpc)

        _logger.error("Now running XMLRPC on http://%s:%s/tribler" % (self.xmlrpc._iface, self.xmlrpc._port))
        self.xmlrpc.start_server()

    def keep_running(self):
        return self.tribler.is_running()

if __name__ == '__main__':
    tsap = TSAP()
    tsap.run()

    # Needed when using the twisted XMLRPC server
    while tsap.keep_running():
        time.sleep(1)

    #tsap.dm.add_torrent("e9776f4626e03405b005ad30b4b4a2906125bd62", "Sintel")
