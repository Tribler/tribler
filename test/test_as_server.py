# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import unittest

import os
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
        LaunchMany.__init__(self,config,display)

    def run(self):
        print "MyLaunchMany: run called by",currentThread().getName()
        LaunchMany.start(self)
        pass    

    def halt(self):
        self.doneflag.set()

    def get_listen_port(self):
        return self.listen_port

class TestAsServer(unittest.TestCase):
    """ 
    Parent class for testing the server-side of Tribler
    """
    
    def setUp(self):
        config_path = tempfile.mkdtemp()
        configdir = ConfigDir('launchmany',config_path)
        defaultsToIgnore = ['responsefile', 'url', 'priority']
        configdir.setDefaults(download_bt1.defaults,defaultsToIgnore)
        #configdir.loadConfig()
        config = configdir.getConfig()
        # extra defaults
        config['torrent_dir'] = '.'
        config['parse_dir_interval'] = 600
        # overrides
        config['config_path'] = config_path
        config['minport'] = random.randint(10000, 60000)
        config['text_mode'] = 1
        config['buddycast'] = 0
        config['superpeer'] = 0
        self.setUpWithConfig(config_path,config)

    def setUpWithConfig(self,config_path,config):
        self.config_path = config_path
        tribler_init(config_path)
        self.lm = MyLaunchMany(config, HeadlessDisplayer(self))
        self.hisport = self.lm.get_listen_port()
        keypair_filename = os.path.join(config_path,'ec.pem')
        self.his_keypair = EC.load_key(keypair_filename)

        self.my_keypair = EC.gen_params(EC.NID_sect233k1)
        self.my_keypair.gen_key()

    def tearDown(self):
        shutil.rmtree(self.config_path)
        self.lm.halt()
