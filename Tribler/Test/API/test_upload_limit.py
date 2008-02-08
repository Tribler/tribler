# Written by Arno Bakker
# see LICENSE.txt for license information
#

import unittest
import os
import sys
import time
import socket
import tempfile
from traceback import print_exc

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.btconn import BTConnection
from Tribler.Core.BitTornado.BT1.MessageID import *

from Tribler.Core.TorrentDef import *
from Tribler.Core.DownloadConfig import *
from Tribler.Core.Session import *
from Tribler.Core.simpledefs import *

from Tribler.Policies.RateManager import UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager
from Tribler.Policies.UploadLimitation import *

DEBUG=True

class TestSeeding(TestAsServer):
    """ 
    Testing seeding via new tribler API:
    """

    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        print >>sys.stderr,"test: Giving Session time to startup"
        time.sleep(5)
        print >>sys.stderr,"test: Session should have started up"
    
    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        
        self.config.set_overlay(False)
        self.config.set_internal_tracker(True)
        
        self.mylistenport = 4810

    def setUpPostSession(self):
        pass
    
    def setup_seeder(self,merkle):
        self.tdef = TorrentDef()
        self.sourcefn = os.path.join(os.getcwd(),"big.wmv")
        self.tdef.add_content(self.sourcefn)
        self.tdef.set_create_merkle_torrent(merkle)
        self.tdef.set_tracker(self.session.get_internal_tracker_url())
        self.tdef.finalize()

        self.torrentfn = os.path.join(self.session.get_state_dir(),"gen.torrent")
        self.tdef.save(self.torrentfn)
        
        print >>sys.stderr,"test: setup_seeder: name is",self.tdef.metainfo['info']['name']

        # set upload limitation
        rateManager = UserDefinedMaxAlwaysOtherwiseEquallyDividedRateManager()
        uploadLimitation = TotalUploadLimitation(self.session,rateManager)
        
        self.dscfg = DownloadStartupConfig()
        self.dscfg.set_dest_dir(os.getcwd())
        self.dscfg.set_max_rate_period(4.0)
        d = self.session.start_download(self.tdef,self.dscfg)
        
        d.set_state_callback(self.seeder_state_callback)
        
    def seeder_state_callback(self,ds):
        d = ds.get_download()
        print >>sys.stderr,"test: seeder:",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(), "up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
        return (1.0,False)


    def test_normal_torrent(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        self.setup_seeder(False)
        #self.subtest_is_seeding()
        self.subtest_download()

    def test_merkle_torrent(self):
        self.setup_seeder(True)
        self.subtest_is_seeding()
        self.subtest_download()

    def subtest_is_seeding(self):
        infohash = self.tdef.get_infohash()
        s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        s.read_handshake_medium_rare()
        
        s.send(CHOKE)
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, peer didn't reply"
            self.assert_(False)
        s.close()
        
        
    def subtest_download(self):
        """ Now download the file via another Session """
        
        self.config2 = self.config.copy() # not really necess
        self.config_path2 = tempfile.mkdtemp()
        self.config2.set_state_dir(self.config_path2)
        self.config2.set_listen_port(self.mylistenport)
        self.session2 = Session(self.config2,ignore_singleton=True)
        
        # Allow session2 to start
        print >>sys.stderr,"test: Sleeping 3 secs to let Session2 start"
        time.sleep(3)
        
        tdef2 = TorrentDef.load(self.torrentfn)

        dscfg2 = DownloadStartupConfig()
        dscfg2.set_dest_dir(self.config_path2)
        
        d = self.session2.start_download(tdef2,dscfg2)
        d.set_state_callback(self.downloader_state_callback)
        time.sleep(1400)
    
    def downloader_state_callback(self,ds):
        d = ds.get_download()
        #print >>sys.stderr,"test: download:",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(), "up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
        
        if ds.get_status() == DLSTATUS_SEEDING:
            # File is in
            destfn = os.path.join(self.config_path2,"big.wmv")
            f = open(destfn,"rb")
            realdata = f.read()
            f.close()
            f = open(self.sourcefn,"rb")
            expdata = f.read()
            f.close()
            
            self.assert_(realdata == expdata)
            return (2.0,True)
        
        return (2.0,False)
        
        
"""
    def subtest_good_nontribler_ut_pex_diff_id(self):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        self._test_good(self.create_good_nontribler_extend_hs,options=options,infohash=self.infohash,pex_id=134)

    def subtest_good_tribler_ut_pex(self):
        self._test_good(self.create_good_tribler_extend_hs,infohash=self.infohash)
        
        # We've said we're a Tribler peer, and we initiated the connection, so 
        # now *we* should now try to establish an overlay-swarm connection.
        s = OLConnection(self.my_keypair,'localhost',self.hisport,mylistenport=self.mylistenport)
        # the connection should be intact, so this should not throw an
        # exception:
        time.sleep(5)
        s.send('bla')
        s.close()

    def _test_good(self,msg_gen_func,options=None,infohash=None,pex_id=1):
        if options is None and infohash is None:
            s = BTConnection('localhost',self.hisport)
        elif options is None:
            s = BTConnection('localhost',self.hisport,user_infohash=infohash)
        elif infohash is None:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options)
        else:
            s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=infohash)
            
        if DEBUG:
            print "test: Creating test HS message",msg_gen_func,"pex_id",pex_id
        msg = msg_gen_func(pex_id=pex_id)
        s.send(msg)
        s.read_handshake_medium_rare()

        # Send our ut_pex message to Tribler
        msg = self.create_good_ut_pex(pex_id=pex_id)
        s.send(msg)
        
        time.sleep(5)

        # Tribler should send an EXTEND HS message back
        try:
            s.s.settimeout(10.0)
            resp = s.recv()
            self.assert_(len(resp) > 0)
            self.assert_(resp[0] == EXTEND)
            self.check_tribler_extend_hs(resp[1:])
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND HS message"
            self.assert_(False)

        # Tribler should send an ut_pex message after a while
        try:
            s.s.settimeout(70.0)
            while True:
                resp = s.recv()
                self.assert_(len(resp) > 0)
                print "test: Tribler returns",getMessageName(resp[0])
                if resp[0] == EXTEND:
                    self.check_ut_pex(resp[1:],pex_id=pex_id)
                    s.close()
                    break
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't reply with EXTEND ut_pex message"
            self.assert_(False)

        

    def create_good_nontribler_extend_hs(self,listenport=None,pex_id=1):
        d = {}
        d['m'] = {'ut_pex':pex_id, 'dag':255 }
        if listenport is None:
            d['p'] = self.mylistenport
        else:
            d['p'] = listenport
        d['v'] = 'TestSweet 1.2.3.4'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def create_good_tribler_extend_hs(self,pex_id=1):
        d = {}
        d['m'] = {'Tr_OVERLAYSWARM':253,'ut_pex':pex_id}
        d['p'] = self.mylistenport
        d['v'] = 'Tribler 3.5.1'
        d['e'] = 0
        bd = bencode(d)
        return EXTEND+chr(0)+bd

    def check_tribler_extend_hs(self,data):
        self.assert_(data[0] == chr(0))
        d = bdecode(data[1:])
        self.assert_(type(d) == DictType)
        self.assert_('m' in d.keys())
        m = d['m']
        self.assert_(type(m) == DictType)
        self.assert_('Tr_OVERLAYSWARM' in m.keys())
        val = m['Tr_OVERLAYSWARM']
        self.assert_(type(val) == IntType)
        self.assert_(val == 253)
        self.assert_('ut_pex' in m.keys())
        val = m['ut_pex']
        self.assert_(type(val) == IntType)
        self.assert_(val == 1)

    def create_good_ut_pex(self,pex_id=1):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(pex_id)+bd

    def check_ut_pex(self,data,pex_id):
        self.assert_(data[0] == chr(pex_id))
        d = bdecode(data[1:])
        self.assert_(type(d) == DictType)
        self.assert_('added' in d.keys())
        cp = d['added']
        apeers = self.check_compact_peers(cp)
        self.assert_('added.f' in d.keys())
        f = d['added.f']
        print "test: Length of added.f",len(f)
        self.assert_(type(f) == StringType)
        self.assert_(len(apeers) == len(f))
        self.assert_('dropped' in d.keys())
        cp = d['dropped']
        self.check_compact_peers(cp)
        
        # Check that the fake client we created is included
        self.assert_(len(apeers) == 1)
        self.assert_(apeers[0][1] == 4321)
        

    def check_compact_peers(self,cp):
        self.assert_(type(cp) == StringType)
        self.assert_(len(cp) % 6 == 0)
        peers = []
        for x in xrange(0, len(cp), 6):
            ip = '.'.join([str(ord(i)) for i in cp[x:x+4]])
            port = (ord(cp[x+4]) << 8) | ord(cp[x+5])
            peers.append((ip, port))
        #print "test: Got compact peers",peers
        return peers

    #
    # Bad EXTEND handshake message
    #    
    def subtest_bad_ut_pex(self):
        methods = [self.create_empty,
            self.create_ext_id_not_byte,
            self.create_not_bdecodable,
            self.create_not_dict1,
            self.create_not_dict2,
            self.create_bad_keys,
            self.create_added_missing,
            self.create_added_f_missing,
            self.create_dropped_missing,
            self.create_added_not_str,
            self.create_added_f_not_str,
            self.create_dropped_not_str,
            self.create_added_too_small,
            self.create_added_f_too_big,
            self.create_dropped_too_small]

        for m in methods:
            self._test_bad(m)

    #
    # Main test code for bad EXTEND ut_pex messages
    #
    def _test_bad(self,gen_drequest_func):
        options = '\x00\x00\x00\x00\x00\x10\x00\x00'
        s = BTConnection('localhost',self.hisport,user_option_pattern=options,user_infohash=self.infohash)
        print >> sys.stderr,"\ntest: ",gen_drequest_func
        
        hsmsg = self.create_good_nontribler_extend_hs()
        s.send(hsmsg)
        
        msg = gen_drequest_func()
        s.send(msg)
        time.sleep(5)
        
        # the other side should not like this and close the connection
        try:
            s.s.settimeout(10.0)
            s.read_handshake_medium_rare(close_ok = True)
            while True:
                resp = s.recv()
                if len(resp) > 0:
                    print >>sys.stderr,"test: Got",getMessageName(resp[0]),"from peer"
                    self.assert_(resp[0] == EXTEND or resp[0]==UNCHOKE)
                else:
                    self.assert_(len(resp)==0)
                    s.close()
                    break
        except socket.timeout:
            print >> sys.stderr,"test: Timeout, bad, peer didn't close connection"
            self.assert_(False)

    #
    # Bad message creators
    # 
    def create_empty(self):
        return EXTEND+chr(1)

    def create_ext_id_not_byte(self):
        return EXTEND+'Hallo kijkbuiskinderen'
    
    def create_not_bdecodable(self):
        return EXTEND+chr(1)+"bla"

    def create_not_dict1(self):
        d = 481
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_not_dict2(self):
        d = []
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_bad_keys(self):
        d = {}
        d['bla1'] = ''
        d['bla2'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd
        
    def create_added_missing(self):
        d = {}
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd
        
    def create_added_f_missing(self):
        d = {}
        d['added'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_missing(self):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_not_str(self):
        d = {}
        d['added'] = 481
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_f_not_str(self):
        d = {}
        d['added'] = ''
        d['added.f'] = 481
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_not_str(self):
        d = {}
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = 481
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_too_small(self):
        d = {}
        d['added'] = '\x82\x25\xc1\x40\x00' # should be 6 bytes
        d['added.f'] = ''
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_added_f_too_big(self):
        d = {}
        d['added'] = ''
        d['added.f'] = '\x00'
        d['dropped'] = ''
        bd = bencode(d)
        return EXTEND+chr(1)+bd

    def create_dropped_too_small(self):
        d = {}        
        d['added'] = ''
        d['added.f'] = ''
        d['dropped'] = '\x82\x25\xc1\x40\x00' # should be 6 bytes
        bd = bencode(d)
        return EXTEND+chr(1)+bd
"""

def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_seeding.py <method name>"
    else:
        suite.addTest(TestSeeding(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
