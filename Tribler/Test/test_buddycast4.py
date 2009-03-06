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


        
        
        
        
        

    
    def get_good_clicklog_msg(self, n):
        if n==1:
            preferences = [["hash1", ["linux","ubuntu"], 1, 2]]
            collected_torrents = ["hash"]
        elif n==2:
            preferences = [["hash2", ["linux", "ubuntu"], 2, 2]]
            collected_torrents = ["hash2"]            
        elif n==3:
            preferences = [["hash3", ["linux","redhat"],5,2]]
            collected_torrents = ['hash3'] 
            
        return {
                'preferences': preferences, 
                'ndls': 1, 
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
        prefmsg = self.get_good_clicklog_msg(i)
        msg = self.create_payload(prefmsg)
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
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)


        # self.getAll("rowid, peer_id, torrent_id, click_position,reranking_strategy", order_by="peer_id, torrent_id")
        real_prefs = pref_db.getAllEntries()
        my_peer_id = real_prefs[0][1] 
        real_terms = term_db.getAllEntries()
        real_search = search_db.getAllEntries()
        
        
        torrent_id = None
        while not torrent_id:
            hash = prefmsg['preferences'][0][0]
            print >> sys.stderr, "hash: %s, bin2str: %s" % (hash, bin2str(hash))
            torrent_data =  torrent_db.getTorrentID(hash)
            print >> sys.stderr, "Torrent data for torrent %s: %s" % (prefmsg['preferences'][0][0], torrent_data)
            torrent_id = torrent_data
            if not torrent_id:
                print >> sys.stderr, "torrent not yet saved, waiting..."
                sleep(1)
        
        
        
        if i==1:
            wanted_prefs = [[1,my_peer_id,1,1,2]]
            wanted_terms = [[1,bin2str(str(u'linux'))], [2,bin2str(str(u'ubuntu'))]]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1]]
        elif i==2:
            wanted_prefs = [[1,my_peer_id,'?',1,2], [2,my_peer_id,torrent_id,2,2]]
            wanted_terms = [[1,bin2str(str(u'linux'))], [2,bin2str(str(u'ubuntu'))]]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1],
                             [3,my_peer_id,'?',1,0],
                             [4,my_peer_id,'?',2,1]]
            
        elif i==3:
            wanted_prefs = [[1,my_peer_id,'?',1,2], [2,my_peer_id,'?',2,2],[3,my_peer_id,torrent_id,5,2]]
            wanted_terms = [[1,bin2str(str(u'linux'))], [2,bin2str(str(u'ubuntu'))], [3, bin2str(str(u'redhat'))]]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1],
                             [3,my_peer_id,'?',1,0],
                             [4,my_peer_id,'?',2,1],
                             [5,my_peer_id,'?',1,0],
                             [6,my_peer_id,'?',3,1]]
            
                
        
        print >> sys.stderr, "real_prefs: %s" % real_prefs
        print >> sys.stderr, "real_terms: %s" % real_terms
        print >> sys.stderr, "real_search: %s " % real_search

        print >> sys.stderr, "wanted_prefs: %s" % wanted_prefs
        print >> sys.stderr, "wanted_terms: %s" % wanted_terms
        print >> sys.stderr, "wanted_search: %s " % wanted_search

        if actuallyTest:
            self.assert_(self.lol_equals(real_search, wanted_search, "good buddycast %d: search" % i))
            self.assert_(self.lol_equals(real_terms, wanted_terms, "good buddycast %d: terms" % i))
            self.assert_(self.lol_equals(real_prefs, wanted_prefs, "good buddycast %d: prefs" % i))
        
    def subtest_terms(self):
        """assumes clicklog message 1 and 2 have been sent and digested"""
        
        term_db = self.session.open_dbhandler(NTFY_TERM)
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport)        
        msg = self.get_good_clicklog_msg(3)
        msg = self.create_payload(msg)
        s.send(msg)
        resp = s.recv()
        
        termid = term_db.getTermID(bin2str(str(u"linux")))
        print >>sys.stderr, "TermID fuer Linux: %s" % termid
        #self.assert_(termid == 1)
        
        #self.assert_(term_db.getTerm(1)==bin2str(str(u"linux")))
        
        completedTerms = term_db.getTermsStartingWith("li")
        print >> sys.stderr, "terms starting with l: %s" % completedTerms  
        self.assert_(len(completedTerms)==1)
        self.assert_(str(u'linux') in completedTerms)



    def subtest_create_mypref(self):
        print "creating test MyPreference data"
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.addInfohash('myhash')
        torrent_id = torrent_db.getTorrentID('myhash')
        mypref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        
        mypref_db.addMyPreference('myhash', {'destination_path':''}, commit=True)
        clicklog_data = {
                            'click_position': 1,
                            'reranking_strategy': 2,
                            'keywords': ['linux', 'fedora']
                        }
        mypref_db.addClicklogToMyPreference('myhash', clicklog_data, commit=True)
        
        # self.getAll("torrent_id, click_position, reranking_strategy", order_by="torrent_id")
        allEntries = mypref_db.getAllEntries()
        print >> sys.stderr, "all mypref entries: %s" % allEntries
        self.assert_(len(allEntries)==1)
        # (torrent_id, click_pos, rerank_strategy)
        mypref_wanted = [['?',1,2]]
        self.assert_(self.lol_equals(allEntries, mypref_wanted, "create mypref all"))
        
        # self.getAll("rowid, peer_id, torrent_id, term_id, term_order ", order_by="rowid")
        real_search = search_db.getAllOwnEntries()
        wanted_search = [[7,0,torrent_id,1,0],
                         [8,0,torrent_id,5,1]] # is now 5 for some reason
        self.assert_(self.lol_equals(real_search, wanted_search, "create mypref allown"))        
        
        
    def subtest_create_bc(self):
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db._db.update("Torrent", status_id=1)
        pref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        pref_db.loadData()
        msg = self.buddycast.buddycast_core.createBuddyCastMessage(0, 8, target_ip="127.0.0.1", target_port=80)
        print >> sys.stderr, "created bc pref: %s" % msg        
        self.assert_(msg['preferences']==[['myhash',['linux','fedora'],1,2]])
        

                
    def lol_equals(self, lol1, lol2, msg):
        ok = True
        for (l1, l2) in zip(lol1, lol2):
            for (e1, e2) in zip(l1, l2):
                if e1=='?' or e2=='?':
                    continue
                if not e1==e2:
                    print >> sys.stderr, "%s != %s!" % (e1, e2)
                    ok = False
                    break
        if not ok:
            print >> sys.stderr, "%s: lol != lol:\nreal   %s\nwanted %s" % (msg, lol1, lol2)
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

