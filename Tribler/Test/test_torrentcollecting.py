# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import sys
import time

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR

from Tribler.Core.Session import Session
from Tribler.community.search.community import SearchCommunity
from Tribler.Core.TorrentDef import TorrentDef
import os
import threading

class TestSeeding(TestAsServer):
    """
    Testing seeding via new tribler API:
    """
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)

        self.session2 = Session(self.config2, ignore_singleton=True)
        self.session2.start()

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        self.config.set_swift_proc(True)
        self.config.set_torrent_collecting(True)
        self.config.set_swift_tunnel_listen_port(self.config.get_listen_port() + 2)

        self.config2 = self.config.copy()  # not really necess
        self.config2.set_state_dir(self.getStateDir(2))
        self.config2.set_listen_port(self.config.get_listen_port() + 10)
        self.config2.set_swift_tunnel_listen_port(self.config2.get_listen_port() + 2)

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        TestAsServer.tearDown(self)

    def _create_and_save_torrent(self, session, filename, createTdef=True):
        if createTdef:
            tdef = TorrentDef()
            sourcefn = os.path.join(BASE_DIR, "API", filename)
            tdef.add_content(sourcefn)
            tdef.set_tracker("http://fake.net/announce")
            tdef.finalize()

            torrentfn = os.path.join(session.get_state_dir(), "gen.torrent")
            tdef.save(torrentfn)
        else:
            tdef = None
            torrentfn = os.path.join(BASE_DIR, "API", filename)

        sdef, swiftpath = session.lm.rtorrent_handler._write_to_collected(torrentfn)
        return tdef.get_id() if tdef else None, sdef.get_id()

    def test_torrent_collecting(self):
        from Tribler.dispersy.candidate import Candidate
        candidate = Candidate(("127.0.0.1", self.session.get_swift_tunnel_listen_port()), True)

        event = threading.Event()

        infohash, roothash = self._create_and_save_torrent(self.session, 'file.wmv')
        self.session2.lm.rtorrent_handler.download_torrent(candidate, infohash, roothash, lambda: event.set(), prio=1, timeout=60)
        assert event.wait(60)

        event.clear()

        infohash, roothash = self._create_and_save_torrent(self.session, 'file2.wmv')
        self.session2.lm.rtorrent_handler.download_torrent(candidate, infohash, roothash, lambda: event.set(), prio=1, timeout=60)
        assert event.wait(60)

        event.clear()

        infohash, roothash = self._create_and_save_torrent(self.session, 'file2.wmv', False)
        self.session2.lm.rtorrent_handler.download_torrent(candidate, infohash, roothash, lambda: event.set(), prio=1, timeout=60)
        assert event.wait(60)
