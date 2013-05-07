# Written by Arno Bakker, heavy modified by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import socket
import tempfile
import threading

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR
from Tribler.Test.btconn import BTConnection
from Tribler.Core.MessageID import *

from Tribler.Core.TorrentDef import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.Session import *
from Tribler.Core.simpledefs import *

class TestSeeding(TestAsServer):
    """
    Testing seeding via new tribler API:
    """
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)

        self.session2 = None
        self.seeding_event = threading.Event()
        self.downloading_event = threading.Event()

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)

        self.config2 = self.config.copy()  # not really necess
        self.config2.set_state_dir(self.getStateDir(2))
        self.config2.set_listen_port(4810)

        self.dscfg2 = DownloadStartupConfig()
        self.dscfg2.set_dest_dir(self.getDestDir(2))

    def setUpPostSession(self):
        pass

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        TestAsServer.tearDown(self)

    def setup_seeder(self, merkle, filename='file.wmv'):
        self.tdef = TorrentDef()
        self.sourcefn = os.path.join(BASE_DIR, "API", filename)
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_tracker("http://fake.net/announce")
        self.tdef.set_create_merkle_torrent(merkle)
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(), "gen.torrent")
        self.tdef.save(self.torrentfn)

        print >> sys.stderr, "test: setup_seeder: name is", self.tdef.metainfo['info']['name']

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(os.path.join(BASE_DIR, "API"))  # basedir of the file we are seeding
        d = self.session.start_download(self.tdef, self.dscfg)
        d.set_state_callback(self.seeder_state_callback)

        print >> sys.stderr, "test: setup_seeder: starting to wait for download to reach seeding state"
        assert self.seeding_event.wait(60)

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, "test: seeder:", `d.get_def().get_name()`, dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_event.set()

        return (1.0, False)

    def test_normal_torrent(self):
        self.setup_seeder(False)
        self.subtest_is_seeding()
        self.subtest_download()

#     def test_merkle_torrent(self):
#         self.setup_seeder(True)
#         self.subtest_is_seeding()
#         self.subtest_download()

    def subtest_is_seeding(self):
        infohash = self.tdef.get_infohash()
        s = BTConnection('localhost', self.hisport, user_infohash=infohash)
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
        self.session2.start()

        time.sleep(5)

        tdef2 = TorrentDef.load(self.torrentfn)

        d = self.session2.start_download(tdef2, self.dscfg2)
        d.set_state_callback(self.downloader_state_callback)

        time.sleep(5)

        d.add_peer(("127.0.0.1", self.hisport))
        assert self.downloading_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, "test: download:", `d.get_def().get_name()`, dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            # File is in
            destfn = os.path.join(self.getStateDir(2), "file.wmv")
            f = open(destfn, "rb")
            realdata = f.read()
            f.close()
            f = open(self.sourcefn, "rb")
            expdata = f.read()
            f.close()

            self.assert_(realdata == expdata)
            self.downloading_event.set()
            return (1.0, True)
        return (1.0, False)
