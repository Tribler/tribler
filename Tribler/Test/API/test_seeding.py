"""
Seeding tests.

Author(s): Arno Bakker, Niels Zeilemaker
"""
import logging
import os
from asyncio import Future

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, dlstatus_strings
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


class TestSeeding(TestAsServer):
    """
    Test whether the seeding works correctly.
    """

    async def setUp(self):
        await super(TestSeeding, self).setUp()
        self.tdef = TorrentDef.load(os.path.join(TESTS_DATA_DIR, 'video.avi.torrent'))
        self.sourcefn = os.path.join(TESTS_DATA_DIR, 'video.avi')

    def setUpPreSession(self):
        super(TestSeeding, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    @timeout(60)
    async def test_seeding(self):
        """
        Test whether a torrent is correctly seeded
        """
        await self.setup_seeder(self.tdef, TESTS_DATA_DIR)
        dscfg = self.dscfg_seed.copy()
        dscfg.set_dest_dir(self.getDestDir())
        download = self.session.ltmgr.start_download(tdef=self.tdef, config=dscfg)
        download.add_peer(("127.0.0.1", self.seeder_session.config.get_libtorrent_port()))
        await download.wait_for_status(DLSTATUS_SEEDING)

        # File is in
        destfn = os.path.join(self.getDestDir(), "video.avi")
        with open(destfn, "rb") as f:
            realdata = f.read()
        with open(self.sourcefn, "rb") as f:
            expdata = f.read()

        self.assertEqual(realdata, expdata)

