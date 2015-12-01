# Written by Arno Bakker, heavy modified by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import socket
import sys
import threading
import time

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, dlstatus_strings
from Tribler.Test.btconn import BTConnection
from Tribler.Test.test_as_server import TESTS_API_DIR, TestAsServer


CHOKE = chr(0)
EXTEND = chr(20)

class TestSeeding(TestAsServer):

    """
    Testing seeding via new tribler API:
    """

    def setUp(self):
        """ override TestAsServer """
        super(TestSeeding, self).setUp()

        self.session2 = None
        self.seeding_event = threading.Event()
        self.downloading_event = threading.Event()

    def setUpPreSession(self):
        """ override TestAsServer """
        super(TestSeeding, self).setUpPreSession()

        self.config.set_libtorrent(True)

        self.config2 = self.config.copy()  # not really necess
        self.config2.set_state_dir(self.getStateDir(2))

        self.dscfg2 = DownloadStartupConfig()
        self.dscfg2.set_dest_dir(self.getDestDir(2))

    def setUpPostSession(self):
        pass

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        super(TestSeeding, self).tearDown()

    def setup_seeder(self, filename='video.avi'):
        self.tdef = TorrentDef()
        self.sourcefn = os.path.join(TESTS_API_DIR, filename)
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_tracker("http://fake.net/announce")
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        self.tdef.save(self.torrentfn)

        self._logger.debug("name is %s", self.tdef.metainfo['info']['name'])

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(TESTS_API_DIR)  # basedir of the file we are seeding
        d = self.session.start_download(self.tdef, self.dscfg)
        d.set_state_callback(self.seeder_state_callback)

        self._logger.debug("starting to wait for download to reach seeding state")
        assert self.seeding_event.wait(60)

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("seeder status: %s %s %s",
                           repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_event.set()

        return 1.0, False

    def test_normal_torrent(self):
        self.setup_seeder()
        self.subtest_is_seeding()
        self.subtest_download()

    def subtest_is_seeding(self):
        infohash = self.tdef.get_infohash()
        s = BTConnection('localhost', self.session.get_listen_port(), user_infohash=infohash)
        s.read_handshake_medium_rare()

        s.send(CHOKE)
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
        except socket.timeout:
            print >> sys.stderr, "test: Timeout, peer didn't reply"
            self.assert_(False)
        s.close()

    def subtest_download(self):
        """ Now download the file via another Session """
        self.session2 = Session(self.config2, ignore_singleton=True)

        upgrader = self.session2.prestart()

        while not upgrader.is_done:
            time.sleep(0.1)
        self.session2.start()
        time.sleep(1)

        time.sleep(5)

        tdef2 = TorrentDef.load(self.torrentfn)

        d = self.session2.start_download(tdef2, self.dscfg2)
        d.set_state_callback(self.downloader_state_callback)

        time.sleep(5)

        d.add_peer(("127.0.0.1", self.session.get_listen_port()))
        assert self.downloading_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download status: %s %s %s",
                           repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_SEEDING:
            # File is in
            destfn = os.path.join(self.getDestDir(2), "video.avi")
            f = open(destfn, "rb")
            realdata = f.read()
            f.close()
            f = open(self.sourcefn, "rb")
            expdata = f.read()
            f.close()

            self.assert_(realdata == expdata)
            self.downloading_event.set()
            return 1.0, True
        return 1.0, False
