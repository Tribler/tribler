# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import unittest

import os
import sys
import tempfile
import random
import shutil
import time
from traceback import print_exc

from M2Crypto import EC

from Tribler.Core.Session import *
from Tribler.Core.SessionConfig import *


DEBUG=False

class TestAsServer(unittest.TestCase):
    """
    Parent class for testing the server-side of Tribler
    """

    def setUp(self):
        """ unittest test setup code """
        self.setUpPreSession()
        self.session = Session(self.config)
        self.hisport = self.session.get_listen_port()
        self.setUpPostSession()

    def setUpPreSession(self):
        """ Should set self.config_path and self.config """
        self.config_path = tempfile.mkdtemp()

        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.config_path)
        self.config.set_listen_port(random.randint(10000, 60000))
        self.config.set_buddycast(False)
        self.config.set_start_recommender(False)
        self.config.set_torrent_checking(False)
        self.config.set_superpeer(False)
        self.config.set_dialback(False)
        self.config.set_social_networking(False)
        self.config.set_remote_query(False)
        self.config.set_internal_tracker(False)
        self.config.set_bartercast(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_dispersy(False)
        self.config.set_install_dir(os.path.abspath(os.path.join(__file__,'..','..','..')))

        self.my_keypair = EC.gen_params(EC.NID_sect233k1)
        self.my_keypair.gen_key()

    def setUpPostSession(self):
        """ Should set self.his_keypair """
        keypair_filename = os.path.join(self.config_path,'ec.pem')
        self.his_keypair = EC.load_key(keypair_filename)

    def tearDown(self):
        """ unittest test tear down code """
        if self.session is not None:
            self.session.shutdown()
            print >>sys.stderr,"test_as_server: sleeping after session shutdown"
            time.sleep(2)
        try:
            shutil.rmtree(self.config_path)
        except:
            # Not fatal if something goes wrong here, and Win32 often gives
            # spurious Permission Denied errors.
            print_exc()
