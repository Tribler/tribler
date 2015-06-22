class TriblerWrapper():
    tribler = None
    dm = None
    tm = None
    cm = None

    def __init__(self):
        self.tribler = TriblerSession()

    def stop(self):
        self.tribler.stop_session()

    def start(self):
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
