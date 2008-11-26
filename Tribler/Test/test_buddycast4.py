# Written by Nicolas Neubauer, modified from test_bartercast.py
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
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

from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler

from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory, BuddyCastCore

from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIRST, OLPROTO_VER_SECOND, OLPROTO_VER_THIRD, OLPROTO_VER_FOURTH, OLPROTO_VER_FIFTH, OLPROTO_VER_SIXTH, OLPROTO_VER_SEVENTH, OLPROTO_VER_EIGHTH, OLPROTO_VER_CURRENT, OLPROTO_VER_LOWEST
from Tribler.Core.simpledefs import *

from Tribler.Core.CacheDB.SqliteCacheDBHandler import *

DEBUG=True

    

class TestBuddyCast(TestAsServer):
    """ 
    Testing BuddyCast 4 protocol interactions:
      * clicklog exchange messages
    """
    
    def setUp(self):
        """ override TestAsServer """
        TestAsServer.setUp(self)
        Rand.load_file('randpool.dat', -1)

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # Enable buddycast
        self.config.set_buddycast(True)
        BuddyCastCore.TESTASSERVER = True
        self.config.set_start_recommender(True)
        self.config.set_bartercast(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        
        self.myhash = sha(self.mypermid).digest()
        
        self.buddycast = BuddyCastFactory.getInstance(superpeer=True)
        self.buddycast.olthread_register(True)
        
#        arg0 = sys.argv[0].lower()
#        if arg0.endswith('.exe'):
#            installdir = os.path.abspath(os.path.dirname(sys.argv[0]))
#        else:
#           installdir = os.getcwd()          
#       self.utility = Utility(installdir)        

        
        # wait for buddycast to have completed on run cycle,
        # seems to create problems otherwise
        while not self.buddycast.ranonce:
            pass
            
    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove('randpool.dat')
        except:
            pass


    # copied from test_bartercast.py up to here

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        #1. test good buddycast messages
        
        
        # please note that this may into problems when real buddycast is going on in paralllel
        # you might want to turn actuallyTestGoodBuddyCast off once it has been ascertained
        # (preferably wihout internet connection ;) that they work
        actuallyTestGoodBuddyCast = True 
        self.subtest_good_buddycast_clicklog(1, actuallyTestGoodBuddyCast)
        self.subtest_good_buddycast_clicklog(2, actuallyTestGoodBuddyCast)
        self.subtest_good_buddycast_clicklog(3, actuallyTestGoodBuddyCast)
        self.subtest_terms()
        self.subtest_create_mypref()
        self.subtest_create_bc()


        # 2. test various bad SOCIAL_OVERLAP messages
        #self.subtest_bad_not_bdecodable()
        
        
        
        
        

    
    def get_good_clicklog_msg(self, n):
        if n==1:
            clicklog  = {
                          'termid2terms':
                          {
                            '1': "linux",
                            '2': "ubuntu"
                          },
                        
                          'torrentdata':
                          {
                            'hash':
                              {
                                'click_position': 1,
                                'reranking_strategy': 2,
                                'search_terms': [1,2]
                              }
                           }
                        }        
            preferences = ['hash'] # assume we only have one torrent whose infohash happends to be 'hash'
            collected_torrents = ['hash'] # same goes for recent ones
            
        elif n==2:
            clicklog  = {
                          'termid2terms':
                          {
                            '1': "linux",
                            '2': "suse" # note that this conflicts with '2' from previous message. this is the realistic case and the receiver must be able to handle this
                          },
                        
                          'torrentdata':
                          {
                            'hash2':
                              {
                                'click_position': 2,
                                'reranking_strategy': 2,
                                'search_terms': [1,2]
                              }
                           }
                        }        
            preferences = ['hash2'] # assume we only have one torrent whose infohash happends to be 'hash'
            collected_torrents = ['hash2'] # same goes for recent ones
            
        elif n==3:
            clicklog  = {
                          'termid2terms':
                          {
                            '1': "linux",
                            '2': "redhat" # note that this conflicts with '2' from previous message. this is the realistic case and the receiver must be able to handle this
                          },
                        
                          'torrentdata':
                          {
                            'hash3':
                              {
                                'click_position': 5,
                                'reranking_strategy': 2,
                                'search_terms': [1,2]
                              }
                           }
                        }        
            preferences = ['hash3'] # assume we only have one torrent whose infohash happends to be 'hash'
            collected_torrents = ['hash3'] # same goes for recent ones
          
            
        return {
                'preferences': preferences, 
                'ndls': 1, 
                'clicklog': clicklog, 
                'permid': self.mypermid,
                'ip': '127.0.0.1', #'130.149.146.117', 
                'taste buddies': [], 
                'name': 'nic', 
                'random peers': [], 
                'collected torrents': collected_torrents, 
                'nfiles': 0, 
                'npeers': 0, 
                'port': self.hisport, 
                'connectable': 1}
            

            
            
    def subtest_good_buddycast_clicklog(self, i, actuallyTest = True):
        """sends two buddy cast messages containing clicklog data,
           then checks in the DB to find out whether the correct
           data was stored.
           
           This in fact checks quite a lot of things.
           For example, the messages always contain terms [1,2]
           
           
           later methods require DB setup from these methods
           in order to perform the DB operations but not the tests
           (which are still somewhat sensible to cooccuring network operations)
           the actual testing can be turned of by actuallyTest=False
           so later tests can still be executed successfully
           """
           
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = self.get_good_clicklog_msg(i)
        msg = self.create_payload(msg)
        s.send(msg)
        resp = s.recv()
        if len(resp)>0:
            print >>sys.stderr,"test: reply message %s:%s" % (getMessageName(resp[0]), resp[1:])
        else:
            print >>sys.stderr,"no reply message"
            
        #if we have survived this, check if the content of the remote database is correct
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        term_db = self.session.open_dbhandler(NTFY_TERM)
        pref_db = self.session.open_dbhandler(NTFY_PREFERENCES)


        
        real_prefs = pref_db.getAllEntries()
        my_peer_id = real_prefs[0][1] 
        real_terms = term_db.getAllEntries()
        real_search = search_db.getAllEntries()
        
        if i==1:
            wanted_prefs = [[1,my_peer_id,1,1,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu']]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1]]
        elif i==2:
            wanted_prefs = [[1,my_peer_id,1,1,2], [2,my_peer_id,2,2,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu'], [3, u'suse']]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1],
                             [3,my_peer_id,'?',1,0],
                             [4,my_peer_id,'?',3,1]]
            
        elif i==3:
            wanted_prefs = [[1,my_peer_id,1,1,2], [2,my_peer_id,2,2,2],[3,my_peer_id,3,5,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu'], [3, u'suse'], [4, u'redhat']]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1],
                             [3,my_peer_id,'?',1,0],
                             [4,my_peer_id,'?',3,1],
                             [5,my_peer_id,'?',1,0],
                             [6,my_peer_id,'?',4,1]]
            
                
        
        print >> sys.stderr, "real_prefs: %s" % real_prefs
        print >> sys.stderr, "real_terms: %s" % real_terms
        print >> sys.stderr, "real_search: %s " % real_search

        print >> sys.stderr, "wanted_prefs: %s" % wanted_prefs
        print >> sys.stderr, "wanted_terms: %s" % wanted_terms
        print >> sys.stderr, "wanted_search: %s " % wanted_search

        if actuallyTest:
            self.assert_(self.lol_equals(real_search, wanted_search))
            self.assert_(self.lol_equals(real_terms, wanted_terms))
            self.assert_(self.lol_equals(real_prefs, wanted_prefs))
        
    def subtest_terms(self):
        """assumes clicklog message 1 and 2 have been sent and digested"""
        
        term_db = self.session.open_dbhandler(NTFY_TERM)
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport)        
        msg = self.get_good_clicklog_msg(3)
        msg = self.create_payload(msg)
        s.send(msg)
        resp = s.recv()
        
        self.assert_(term_db.getTermID(u"linux") == 1)
        self.assert_(term_db.getTerm(1)==u"linux")
        
        completedTerms = term_db.getTermsStartingWith("l")
        print >> sys.stderr, "terms starting with l: %s" % completedTerms  
        self.assert_(len(completedTerms)==1)
        self.assert_(u'linux' in completedTerms)



    def subtest_create_mypref(self):
        print "creating test MyPreference data"
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.addInfohash('myhash')
        mypref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        
        mypref_db.addMyPreference('myhash', {'destination_path':''}, commit=True)
        clicklog_data = {
                            'click_position': 1,
                            'reranking_strategy': 2,
                            'keywords': ['linux', 'fedora']
                        }
        mypref_db.addClicklogToMyPreference('myhash', clicklog_data, commit=True)
        
        allEntries = mypref_db.getAllEntries()
        print "all mypref entries: %s" % allEntries
        self.assert_(len(allEntries)==1)
        # (torrent_id, click_pos, rerank_strategy)
        mypref_wanted = [['?',1,2]]
        self.assert_(self.lol_equals(allEntries, mypref_wanted))
        
        real_search = search_db.getAllOwnEntries()
        wanted_search = [[7,0,'?',1,0],
                         [8,0,'?',5,1]]
        self.assert_(self.lol_equals(real_search, wanted_search))        
        
        
    def subtest_create_bc(self):
        msg = self.buddycast.buddycast_core.createBuddyCastMessage(0, 8, target_ip="127.0.0.1", target_port=80)
        self.assert_(msg['preferences']==['myhash'])
        clicklog = msg['clicklog']
        print >> sys.stderr, "created bc.clicklog: %s" % clicklog
        torrentdata = clicklog['torrentdata']
        self.assert_(len(torrentdata)==1)
        torrent_id = torrentdata.keys()[0]
        singletorrentdata = torrentdata[torrent_id]
        self.assert_(singletorrentdata['click_position']==1)
        self.assert_(singletorrentdata['search_terms']==[1,5])
        self.assert_(singletorrentdata['reranking_strategy']==2)
        self.assert_(clicklog['termid2terms']['1']==u'linux')
        self.assert_(clicklog['termid2terms']['5']==u'fedora')
        self.assert_(len(clicklog['termid2terms'])==2)
        #clicklog = 
        #    {'torrentdata': {4: {'click_position': 1, 'search_terms': [1, 5], 'reranking_strategy': 2}}, 
        #              'termid2terms': {1: u'star', 5: u'search'}}, 
        
                
    def lol_equals(self, lol1, lol2):
        ok = True
        for (l1, l2) in zip(lol1, lol2):
            for (e1, e2) in zip(l1, l2):
                if e1=='?' or e2=='?':
                    continue
                if not e1==e2:
                    print "%s != %s!" % (e1, e2)
                    ok = False
                    break
        if not ok:
            print "lol != lol:\n%s\n%s" % (lol1, lol2)
        return ok
        

        
    
        
    def create_payload(self,r):
        return BUDDYCAST+bencode(r)


        
        
    def subtest_bad_not_bdecodable(self):
        self._test_bad(self.create_not_bdecodable)
        
    def create_not_bdecodable(self):
        return BUDDYCAST+"bla"        
        
    def _test_bad(self,gen_soverlap_func):
        print >>sys.stderr,"test: bad BUDDYCAST",gen_soverlap_func
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = gen_soverlap_func()
        s.send(msg)
        time.sleep(5)
        # the other side should not like this and close the connection
        x = s.recv()
        print "response: %s" % x
        self.assert_(len(x)==0)
        s.close()
        
        
        
        
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestBuddyCast))
    #suite.addTest(unittest.makeSuite(TestBuddyCastNonServer))
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

