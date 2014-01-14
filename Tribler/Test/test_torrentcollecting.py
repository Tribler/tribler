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
from shutil import copy, move
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Main.globals import DefaultDownloadStartupConfig
from traceback import print_exc
from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING, \
    STATEDIR_SWIFTRESEED_DIR

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
        infohash3, roothash3 = self._create_and_save_torrent(self.session, 'file2.wmv', False)

        from Tribler.dispersy.candidate import Candidate
        candidate = Candidate(("127.0.0.1", self.session.get_swift_tunnel_listen_port()), True)

        event = threading.Event()
        starttime = time.time()
        self.session2.lm.rtorrent_handler.download_torrent(candidate, infohash3, roothash3, lambda filename: event.set(), prio=1, timeout=60)
        assert event.wait(60)
        print >> sys.stderr, "took", time.time() - starttime

    def _create_and_reseed(self, session):
        # 1. Create a 500K randomdata file
        storagepath = os.path.join(self.getDestDir(), "output_file")
        with open(storagepath, 'wb') as fout:
            fout.write(os.urandom(512000))

        # 2. Create the SwiftDef
        sdef = SwiftDef()
        sdef.set_tracker("127.0.0.1:%d" % session.get_swift_dht_listen_port())
        sdef.add_content(storagepath)
        sdef.finalize(session.get_swift_path(), destdir=self.getDestDir())

        # 3. Save swift files to metadata dir
        metadir = session.get_swift_meta_dir()
        metapath = os.path.join(metadir, "output_file")
        try:
            move(storagepath + '.mhash', metapath + '.mhash')
            move(storagepath + '.mbinmap', metapath + '.mbinmap')
        except:
            print_exc()

        # 4. Start seeding this file
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        dscfg.set_dest_dir(storagepath)
        d = session.start_download(sdef, dscfg)
        d.set_state_callback(self.seeder_state_callback)

        return sdef.get_id()

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, long(time.time()), "test: seeder:", `d.get_def().get_name()`, dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_event.set()
        return (1.0, False)

    def test_with_metadatadir(self):
        roothash = self._create_and_reseed(self.session)
        assert self.seeding_event.wait(60)

        self.test_torrent_collecting()
