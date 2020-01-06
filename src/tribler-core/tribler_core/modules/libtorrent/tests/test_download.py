import os
import shutil
from urllib.request import pathname2url

from tribler_common.simpledefs import DLSTATUS_DOWNLOADING

from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout


class TestDownload(TestAsServer):

    """
    Testing of a torrent download via new tribler API:
    """
    def setUpPreSession(self):
        super(TestDownload, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_libtorrent_max_conn_download(2)

    @timeout(60)
    async def test_download_torrent_from_url(self):
        # Setup file server to serve torrent file
        files_path = self.session_base_dir / 'http_torrent_files'
        files_path.mkdir()
        shutil.copyfile(TORRENT_UBUNTU_FILE, files_path / 'ubuntu.torrent')
        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        d = await self.session.ltmgr.start_download_from_uri(f'http://localhost:{file_server_port}/ubuntu.torrent')
        await d.wait_for_status(DLSTATUS_DOWNLOADING)

    @timeout(60)
    async def test_download_torrent_from_file(self):
        d = await self.session.ltmgr.start_download_from_uri('file:' + pathname2url(str(TORRENT_UBUNTU_FILE)))
        await d.wait_for_status(DLSTATUS_DOWNLOADING)
