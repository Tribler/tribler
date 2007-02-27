# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import unittest

import os
import sys
import tempfile
import random
import shutil
import time
from binascii import b2a_hex
from struct import pack,unpack
from StringIO import StringIO
from threading import Thread,currentThread
from types import DictType, StringType

import BitTornado.download_bt1 as download_bt1
from BitTornado.launchmanycore import LaunchMany
from BitTornado.ConfigDir import ConfigDir
from BitTornado.bencode import bencode,bdecode
from Tribler.__init__ import tribler_init
from M2Crypto import EC

DEBUG=False

class HeadlessDisplayer:
    def __init__(self,testcase):
        self.testcase = testcase
    
    def display(self, data):
        return False
            
    def message(self, s):
        pass

    def exception(self, s):
        self.testcase.assert_(False,"Server threw exception:"+s)

# Thread must come as first parent class!
class MyLaunchMany(Thread,LaunchMany):
    def __init__(self,config,display):
        Thread.__init__(self)
        self.setDaemon(True)
        LaunchMany.__init__(self,config,display)

    def run(self):
        print >> sys.stderr,"MyLaunchMany: run called by",currentThread().getName()
        LaunchMany.start(self)
        pass    

    def halt(self):
        self.doneflag.set()
        print >> sys.stderr,"MyLaunchMany: halt called by",currentThread().getName(),"now waiting for us to stop"
        self.join()

    def get_listen_port(self):
        return self.listen_port

class TestAsServer(unittest.TestCase):
    """ 
    Parent class for testing the server-side of Tribler
    """
    
    def setUp(self):
        """ unittest test setup code """
        self.setUpPreTriblerInit()
        tribler_init(self.config_path,self.install_path)
        self.setUpPreLaunchMany()
        self.lm = MyLaunchMany(self.config, HeadlessDisplayer(self))
        self.hisport = self.lm.get_listen_port()
        self.lm.start()

    def setUpPreTriblerInit(self):
        """ Should set self.config_path and self.config """
        self.config_path = tempfile.mkdtemp()
        self.install_path = '.'
        configdir = ConfigDir('launchmany',self.config_path)
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(download_bt1.defaults,defaultsToIgnore)
        #configdir.loadConfig()
        self.config = configdir.getConfig()
        # extra defaults
        self.config['torrent_dir'] = os.path.join('test','empty_dir')
        self.config['parse_dir_interval'] = 600
        # overrides
        self.config['config_path'] = self.config_path
        self.config['minport'] = random.randint(10000, 60000)
        self.config['text_mode'] = 1
        self.config['buddycast'] = 0
        self.config['superpeer'] = 0
        self.config['dialback'] = 0

        self.my_keypair = EC.gen_params(EC.NID_sect233k1)
        self.my_keypair.gen_key()

    def setUpPreLaunchMany(self):
        """ Should set self.his_keypair """
        keypair_filename = os.path.join(self.config_path,'ec.pem')
        self.his_keypair = EC.load_key(keypair_filename)

    def tearDown(self):
        """ unittest test tear down code """
        shutil.rmtree(self.config_path)
        self.lm.halt()
