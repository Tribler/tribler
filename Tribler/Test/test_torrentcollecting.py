# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
import sys
import time
from shutil import move
import threading
from traceback import print_exc

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR

from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING
from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Swift.SwiftDef import SwiftDef

from Tribler.Main.globals import DefaultDownloadStartupConfig


class TestTorrentCollecting(TestAsServer):
    """
    Testing seeding via new tribler API:
    """
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)

        self.session2 = Session(self.config2, ignore_singleton=True)
        self.session2.start()

        self.seeding_event = threading.Event()

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        self.config.set_swift_proc(True)
        self.config.set_torrent_collecting(True)
        self.config.set_mainline_dht(True)

        self.config2 = self.config.copy()
        self.config2.set_state_dir(self.getStateDir(2))

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        TestAsServer.tearDown(self)

    def _create_and_save_torrent(self, session, filename):
        tdef = TorrentDef()
        sourcefn = os.path.join(BASE_DIR, "API", filename)
        tdef.add_content(sourcefn)
        tdef.set_tracker("http://fake.net/announce")
        tdef.finalize()

        torrentfn = os.path.join(session.get_state_dir(), "gen.torrent")
        tdef.save(torrentfn)

        sdef, swiftpath = session.lm.rtorrent_handler._move_to_collected(torrentfn)
        return tdef.get_id(), sdef.get_id()

    def test_torrent_collecting(self):
        infohash, roothash = self._create_and_save_torrent(self.session, 'video2.avi')

        from Tribler.dispersy.candidate import Candidate
        candidate = Candidate(("127.0.0.1", self.session.get_swift_tunnel_listen_port()), True)

        event = threading.Event()
        starttime = time.time()
        self.session2.lm.rtorrent_handler.download_torrent(candidate, infohash, roothash, lambda filename: event.set(), prio=1, timeout=60)

        assert event.wait(60)
        print >> sys.stderr, "took", time.time() - starttime

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, long(time.time()), "test: seeder:", `d.get_def().get_name()`, dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_event.set()
        return (1.0, False)
