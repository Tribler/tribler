from binascii import hexlify
import logging
import os
import shutil
from unittest import skip
from twisted.internet.defer import Deferred
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_DOWNLOADING
from Tribler.Test.common import UBUNTU_1504_INFOHASH, TORRENT_FILE
from Tribler.Test.test_as_server import TestAsServer


class TestDownload(TestAsServer):

    """
    Testing of a torrent download via new tribler API:
    """

    def __init__(self, *argv, **kwargs):
        super(TestDownload, self).__init__(*argv, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.test_deferred = Deferred()

    def setUpPreSession(self):
        super(TestDownload, self).setUpPreSession()

        self.config.set_libtorrent(True)
        self.config.set_dispersy(False)
        self.config.set_libtorrent_max_conn_download(2)

    def on_download(self, download):
        self._logger.debug("Download started: %s", download)
        download.set_state_callback(self.downloader_state_callback)

    @deferred(timeout=60)
    def test_download_torrent_from_url(self):
        # Setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        d = self.session.start_download_from_uri('http://localhost:%s/ubuntu.torrent' % file_server_port)
        d.addCallback(self.on_download)
        return self.test_deferred

    @skip("Fetching a torrent from the external network is unreliable")
    @deferred(timeout=60)
    def test_download_torrent_from_magnet(self):
        magnet_link = 'magnet:?xt=urn:btih:%s' % hexlify(UBUNTU_1504_INFOHASH)
        d = self.session.start_download_from_uri(magnet_link)
        d.addCallback(self.on_download)
        return self.test_deferred

    @deferred(timeout=60)
    def test_download_torrent_from_file(self):
        from urllib import pathname2url
        d = self.session.start_download_from_uri('file:' + pathname2url(TORRENT_FILE))
        d.addCallback(self.on_download)
        return self.test_deferred

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download status: %s %s %s",
                           repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_DOWNLOADING:
            self.test_deferred.callback(None)
            return 0.0, False

        return 1.0, False
