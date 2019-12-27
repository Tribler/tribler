import os
import shutil
from urllib.request import pathname2url

from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


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
        files_path = os.path.join(self.session_base_dir, 'http_torrent_files')
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, os.path.join(files_path, 'ubuntu.torrent'))
        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        d = await self.session.ltmgr.start_download_from_uri('http://localhost:%s/ubuntu.torrent' % file_server_port)
        await d.wait_for_status(DLSTATUS_DOWNLOADING)

    @timeout(60)
    async def test_download_torrent_from_file(self):
        d = await self.session.ltmgr.start_download_from_uri('file:' + pathname2url(TORRENT_UBUNTU_FILE))
        await d.wait_for_status(DLSTATUS_DOWNLOADING)
