# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import unittest

import os
import sys
import tempfile
import random
import shutil
import time
import gc
from traceback import print_exc

from M2Crypto import EC
from threading import enumerate as enumerate_threads


from Tribler.Core.Session import *
from Tribler.Core.SessionConfig import *
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))

DEBUG = False

class TestAsServer(unittest.TestCase):
    """
    Parent class for testing the server-side of Tribler
    """

    def setUp(self):
        """ unittest test setup code """
        self.setUpPreSession()

        self.session = Session(self.config)
        self.session.start()

        self.hisport = self.session.get_listen_port()

        while not self.session.lm.initComplete:
            time.sleep(1)

    def setUpPreSession(self):
        """ Should set self.config_path and self.config """
        self.config_path = tempfile.mkdtemp()

        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.config_path)
        self.config.set_listen_port(random.randint(10000, 60000))
        self.config.set_torrent_checking(False)
        self.config.set_dialback(False)
        self.config.set_internal_tracker(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_swift_proc(False)
        self.config.set_mainline_dht(False)
        self.config.set_install_dir(os.path.abspath(os.path.join(__file__, '..', '..', '..')))

    def tearDown(self):
        """ unittest test tear down code """
        if self.session is not None:
            self._shutdown_session(self.session)
            Session.del_instance()

        ts = enumerate_threads()
        print >> sys.stderr, "test_as_server: Number of threads still running", len(ts)
        for t in ts:
            print >> sys.stderr, "test_as_server: Thread still running", t.getName(), "daemon", t.isDaemon(), "instance:", t

        SQLiteCacheDB.delInstance()
        from Tribler.Core.CacheDB.sqlitecachedb import unregister
        unregister()

        time.sleep(10)
        gc.collect()

        try:
            shutil.rmtree(self.config_path)
        except:
            # Not fatal if something goes wrong here, and Win32 often gives
            # spurious Permission Denied errors.
            print_exc()

    def _shutdown_session(self, session):
        session_shutdown_start = time.time()
        waittime = 60

        session.shutdown()
        while not session.has_shutdown():
            diff = time.time() - session_shutdown_start
            if diff > waittime:
                print >> sys.stderr, "test_as_server: NOT Waiting for Session to shutdown, took too long"
                break

            print >> sys.stderr, "test_as_server: ONEXIT Waiting for Session to shutdown, will wait for an additional %d seconds" % (waittime - diff)
            time.sleep(1)

        print >> sys.stderr, "test_as_server: Session is shutdown"
