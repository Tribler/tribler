from binascii import hexlify
import logging
import os
import shutil
import threading
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_DOWNLOADING
from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.test_libtorrent_download import TORRENT_FILE


class TestDownload(TestAsServer):

    """
    Testing of a torrent download via new tribler API:
    """

    def __init__(self, *argv, **kwargs):
        super(TestDownload, self).__init__(*argv, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

    def setUp(self):
        """ override TestAsServer """
        super(TestDownload, self).setUp()

        self.downloading_event = threading.Event()

    def setUpPreSession(self):
        """ override TestAsServer """
        super(TestDownload, self).setUpPreSession()

        self.config.set_libtorrent(True)

    def setUpPostSession(self):
        pass

    def test_download_torrent_from_url(self):
        # Setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = get_random_port()
        self.setUpFileServer(file_server_port, files_path)

        d = self.session.start_download_from_uri('http://localhost:%s/ubuntu.torrent' % file_server_port)
        self._logger.debug("Download started: %s", d)
        d.set_state_callback(self.downloader_state_callback)
        assert self.downloading_event.wait(60)

    def test_download_torrent_from_magnet(self):
        magnet_link = 'magnet:?xt=urn:btih:%s' % hexlify(UBUNTU_1504_INFOHASH)
        d = self.session.start_download_from_uri(magnet_link)
        self._logger.debug("Download started: %s", d)
        d.set_state_callback(self.downloader_state_callback)
        assert self.downloading_event.wait(60)

    def test_download_torrent_from_file(self):
        from urllib import pathname2url
        d = self.session.start_download_from_uri('file:' + pathname2url(TORRENT_FILE))
        self._logger.debug("Download started: %s", d)
        d.set_state_callback(self.downloader_state_callback)
        assert self.downloading_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download status: %s %s %s",
                           repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_DOWNLOADING:
            self.downloading_event.set()

        return 1.0, False
