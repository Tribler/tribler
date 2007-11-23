# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import wx
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType
from threading import Thread
from time import sleep
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Main.Dialogs.MugshotManager import MugshotManager,ICON_MAX_SIZE

DEBUG=True

class wxServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)
        
        app = wx.App(0)
        app.MainLoop()


class TestSocialOverlap(TestAsServer):
    """ 
    Testing SOCIAL_OVERLAP message of Social Network extension V1
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        Rand.load_file('randpool.dat', -1)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # Enable social networking
        self.config.set_social_networking(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.wxs = wxServer()
        self.wxs.start()
        print "Sleeping to allow wxServer to start"
        sleep(4)

        self.mm = MugshotManager.getInstance()
        self.mm.register(self.config.sessconfig)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        
        self.myhash = sha(self.mypermid).digest()

        # Give him a usericon to send
        self.mm.copy_file(self.hispermid,self.make_filename('usericon-ok.jpg'))

        self.count = 48

    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove('randpool.dat')
        except:
            pass

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # 1. test good SOCIAL_OVERLAP
        self.subtest_good_soverlap()


        # 2. test various bad SOCIAL_OVERLAP messages
        self.subtest_bad_not_bdecodable()
        self.subtest_bad_not_dict1()
        self.subtest_bad_not_dict2()
        self.subtest_bad_empty_dict()
        self.subtest_bad_wrong_dict_keys()

        self.subtest_bad_persinfo()
        

    #
    # Good SOCIAL_OVERLAP
    #
    def subtest_good_soverlap(self):
        """ 
            test good SOCIAL_OVERLAP messages
        """
        print >>sys.stderr,"test: good SOCIAL_OVERLAP"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.create_good_soverlap()
        s.send(msg)
        resp = s.recv()
        self.assert_(resp[0] == SOCIAL_OVERLAP)
        self.check_soverlap(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_soverlap(self):
        d = {}
        [pi_sig,pi] = self.create_good_persinfo()

        d['persinfo'] = pi
        return self.create_payload(d)

    def create_good_persinfo(self):
        pi = {}
        pi['name'] = 'Beurre Alexander Lucas'
        pi['icontype'] = 'image/jpeg'
        pi['icondata'] = self.read_usericon_ok()
        sig = None
        return [sig,pi]

    def read_usericon_ok(self):
        return self.read_file(self.make_filename('usericon-ok.jpg'))

    def make_filename(self,filename):
        """ Test assume to be run from new Tribler/Test """
        return filename

    def read_file(self,filename):
        f = open( filename, 'rb')
        data = f.read()
        f.close()
        return data
    
    def create_payload(self,r):
        return SOCIAL_OVERLAP+bencode(r)

    def check_soverlap(self,data):
        d = bdecode(data)
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('persinfo'))
        self.check_persinfo(d['persinfo'])

    def check_persinfo(self,d):
        self.assert_(type(d) == DictType)
        print "test: persinfo: keys is",d.keys()

        self.assert_(d.has_key('name'))
        self.assert_(isinstance(d['name'],str))
        self.assert_(d.has_key('icontype'))
        self.assert_(d.has_key('icondata'))
        self.check_usericon(d['icontype'],d['icondata'])

    def check_usericon(self,icontype,icondata):
        self.assert_(type(icontype) == StringType)
        self.assert_(type(icondata) == StringType)
        idx = icontype.find('/')
        ridx = icontype.rfind('/')
        self.assert_(idx != -1)
        self.assert_(idx == ridx)
        self.assert_(len(icondata) <= ICON_MAX_SIZE)
        print "check_usericon: len icon is",len(icondata)

    # Bad soverlap
    #    
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)

    def subtest_bad_not_dict1(self):
        self._test_bad(self.create_not_dict1)

    def subtest_bad_not_dict2(self):
        self._test_bad(self.create_not_dict2)

    def subtest_bad_empty_dict(self):
        self._test_bad(self.create_empty_dict)

    def subtest_bad_wrong_dict_keys(self):
        self._test_bad(self.create_wrong_dict_keys)

    #
    # Bad 'persinfo' 
    #
    def subtest_bad_persinfo(self):
        """ Cut a corner """
        methods = [
            self.make_persinfo_not_dict1,
            self.make_persinfo_not_dict2,
            self.make_persinfo_empty_dict,
            self.make_persinfo_wrong_dict_keys,
            self.make_persinfo_name_not_str,
            self.make_persinfo_icontype_not_str,
            self.make_persinfo_icontype_noslash,
            self.make_persinfo_icondata_not_str,
            self.make_persinfo_icondata_too_big ]
        for method in methods:
            # Hmmm... let's get dirty
            print >> sys.stderr,"\ntest: ",method,
            func = lambda: self.create_bad_persinfo(method)
            self._test_bad(func)

    def _test_bad(self,gen_soverlap_func):
        print >>sys.stderr,"test: bad SOCIAL_OVERLAP",gen_soverlap_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_soverlap_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assert_(len(s.recv())==0)
        s.close()

    def create_not_bdecodable(self):
        return SOCIAL_OVERLAP+"bla"

    def create_not_dict1(self):
        soverlap = 481
        return self.create_payload(soverlap)

    def create_not_dict2(self):
        soverlap = []
        return self.create_payload(soverlap)

    def create_empty_dict(self):
        soverlap = {}
        return self.create_payload(soverlap)

    def create_wrong_dict_keys(self):
        soverlap = {}
        soverlap['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        soverlap['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_payload(soverlap)


    #
    # Bad persinfo
    #
    def create_bad_persinfo(self,gen_persinfo_func):
        soverlap = {}
        pi = gen_persinfo_func()
        soverlap['persinfo'] = pi
        return self.create_payload(soverlap)

    def make_persinfo_not_dict1(self):
        return 481

    def make_persinfo_not_dict2(self):
        return []

    def make_persinfo_empty_dict(self):
        return {}

    def make_persinfo_wrong_dict_keys(self):
        pi = {}
        pi['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        pi['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return pi

    def make_persinfo_name_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['name'] = 481
        return pi

    def make_persinfo_icontype_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icontype'] = 481
        return pi

    def make_persinfo_icontype_noslash(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icontype'] = 'image#jpeg'
        return pi

    def make_persinfo_icondata_not_str(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icondata'] = 481
        return pi

    def make_persinfo_icondata_too_big(self):
        [sig,pi] = self.create_good_persinfo()
        pi['icondata'] = "".zfill(ICON_MAX_SIZE+100)
        return pi

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSocialOverlap))
    
    return suite

def sign_data(plaintext,keypair):
    digest = sha(plaintext).digest()
    return keypair.sign_dsa_asn1(digest)

def verify_data(plaintext,permid,blob):
    pubkey = EC.pub_key_from_der(permid)
    digest = sha(plaintext).digest()
    return pubkey.verify_dsa_asn1(digest,blob)


if __name__ == "__main__":
    unittest.main()

