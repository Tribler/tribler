import logging
import os
import shutil
from asyncio import Future
from urllib.request import pathname2url

from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, dlstatus_strings
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


class TestDownload(TestAsServer):

    """
    Testing of a torrent download via new tribler API:
    """

    def __init__(self, *argv, **kwargs):
        super(TestDownload, self).__init__(*argv, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.test_future = Future()

    def setUpPreSession(self):
        super(TestDownload, self).setUpPreSession()

        self.config.set_libtorrent_enabled(True)
        self.config.set_libtorrent_max_conn_download(2)

    def on_download(self, download):
        self._logger.debug("Download started: %s", download)
        download.set_state_callback(self.downloader_state_callback)

    @timeout(60)
    async def test_download_torrent_from_url(self):
        # Setup file server to serve torrent file
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        d = await self.session.ltmgr.start_download_from_uri('http://localhost:%s/ubuntu.torrent' % file_server_port)
        self.on_download(d)
        return self.test_future

    @timeout(60)
    async def test_download_torrent_from_file(self):
        d = await self.session.ltmgr.start_download_from_uri('file:' + pathname2url(TORRENT_UBUNTU_FILE))
        self.on_download(d)
        return self.test_future

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download status: %s %s %s",
                           repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_DOWNLOADING:
            self.test_future.set_result(None)
            return 0.0

        return 1.0
