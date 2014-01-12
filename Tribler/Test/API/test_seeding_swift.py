# Written by Arno Bakker, heavy modified by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import shutil
import threading

from Tribler.Test.test_as_server import TestAsServer, BASE_DIR

from Tribler.Core.DownloadConfig import *
from Tribler.Core.Session import *
from Tribler.Core.simpledefs import *
from Tribler.Core.Swift.SwiftDef import SwiftDef

from unittest.case import skip


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
        self.config.set_swift_proc(True)
        self.config.set_install_dir(os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', '..')))

        self.config2 = self.config.copy()  # not really necess
        self.config2.set_state_dir(self.getStateDir(2))

    def setUpPostSession(self):
        pass

    def tearDown(self):
        if self.session2:
            self._shutdown_session(self.session2)
            time.sleep(10)

        TestAsServer.tearDown(self)

    def setup_seeder(self, filenames):
        self.filenames = filenames

        self.sdef = SwiftDef()
        self.sdef.set_tracker("127.0.0.1:%d" % self.session.get_swift_dht_listen_port())

        destdir = os.path.join(BASE_DIR, "API")

        for f in filenames:
            if len(filenames) == 1:
                self.sdef.add_content(os.path.join(destdir, f))
            else:
                xi = f
                if sys.platform == "win32":
                    xi = xi.replace("\\", "/")
                si = xi.encode("UTF-8")
                self.sdef.add_content(os.path.join(destdir, f), si)

        specpn = self.sdef.finalize(self.session.get_swift_path(), destdir=destdir)

        metadir = self.session.get_swift_meta_dir()
        if len(filenames) == 1:
            storagepath = os.path.join(destdir, filenames[0])  # Point to file on disk
            metapath = os.path.join(metadir, os.path.split(storagepath)[1])

            try:
                shutil.move(storagepath + '.mhash', metapath + '.mhash')
                shutil.move(storagepath + '.mbinmap', metapath + '.mbinmap')
            except:
                print_exc()
        else:
            metapath = os.path.join(metadir, self.sdef.get_roothash_as_hex())
            storagepath = destdir

            # Reuse .mhash and .mbinmap (happens automatically for single-file)
            try:
                shutil.move(specpn, metapath + '.mfspec')
                shutil.move(specpn + '.mhash', metapath + '.mhash')
                shutil.move(specpn + '.mbinmap', metapath + '.mbinmap')
            except:
                print_exc()

        print >> sys.stderr, "test: setup_seeder: seeding", filenames

        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(storagepath)

        d = self.session.start_download(self.sdef, self.dscfg)
        d.set_state_callback(self.seeder_state_callback)

        print >> sys.stderr, "test: setup_seeder: starting to wait for download to reach seeding state"
        assert self.seeding_event.wait(60)
        return self.sdef.get_roothash()

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, "test: seeder:", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_event.set()

        return (1.0, False)

    def setup_downloader(self, roothash, filenames):
        self.session2 = Session(self.config2, ignore_singleton=True)
        self.session2.start()

        time.sleep(5)

        sdef2 = SwiftDef(roothash, tracker="127.0.0.1:%d" % self.session.get_swift_tunnel_listen_port())

        self.dscfg2 = DownloadStartupConfig()
        self.dscfg2.set_dest_dir(os.path.join(self.getDestDir(2), filenames[0]) if len(filenames) == 1 else self.getDestDir(2))
        self.dscfg2.set_swift_meta_dir(self.getDestDir(2))

        d = self.session2.start_download(sdef2, self.dscfg2)
        d.set_state_callback(self.downloader_state_callback)
        assert self.downloading_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        print >> sys.stderr, "test: downloader:", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()], ds.get_progress()

        if ds.get_status() == DLSTATUS_SEEDING:
            for filename in self.filenames:
                destfn = os.path.join(self.getDestDir(2), filename)
                f = open(destfn, "rb")
                realdata = f.read()
                f.close()
                f = open(os.path.join(BASE_DIR, "API", filename), "rb")
                expdata = f.read()
                f.close()
                self.assert_(realdata == expdata)

            self.downloading_event.set()
            return (1.0, True)
        return (1.0, False)

    def test_singlefile_swift(self):
        filenames = ['file.wmv']
        roothash = self.setup_seeder(filenames)
        self.setup_downloader(roothash, filenames)

    def test_multifile_swift(self):
        filenames = ['file.wmv', 'file2.wmv']
        roothash = self.setup_seeder(filenames)
        self.setup_downloader(roothash, filenames)

    def test_multifile_swift_with_subdirs(self):
        filenames = ['file.wmv', 'contentdir\\file.avi']
        roothash = self.setup_seeder(filenames)
        self.setup_downloader(roothash, filenames)
