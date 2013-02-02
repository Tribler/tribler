# Written by Nicolas Neubauer, Arno Bakker
# see LICENSE.txt for license information
#
# Test case for BuddyCast overlay version 12 (and 8). To be integrated into
# test_buddycast_msg.py
#
# Very sensitive to the order in which things are put into DB,
# so not a robust test


import unittest
import os
import sys
import time
import tempfile
import shutil
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType
from threading import Thread
from time import sleep
from M2Crypto import Rand,EC


from Tribler.Test.test_as_server import TestAsServer
from olconn import OLConnection
from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.MessageID import *

from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler

from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory, BuddyCastCore

from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FIRST, OLPROTO_VER_SECOND, OLPROTO_VER_THIRD, OLPROTO_VER_FOURTH, OLPROTO_VER_FIFTH, OLPROTO_VER_SIXTH, OLPROTO_VER_SEVENTH, OLPROTO_VER_EIGHTH, OLPROTO_VER_ELEVENTH, OLPROTO_VER_CURRENT, OLPROTO_VER_LOWEST
from Tribler.Core.simpledefs import *

from Tribler.Core.CacheDB.SqliteCacheDBHandler import *
from Tribler.Core.CacheDB.sqlitecachedb import CURRENT_MAIN_DB_VERSION

DEBUG=True

    

class TestBuddyCastMsg8Plus(TestAsServer):
    """ 
    Testing BuddyCast 5 / overlay protocol v12+v8 interactions:
    swarm size info exchange.
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
        
        # Arno, 2010-02-02: Install empty superpeers.txt so no interference from 
        # real BuddyCast.
        self.config.set_crawler(False)
        
        # Write superpeers.txt
        self.install_path = tempfile.mkdtemp()
        spdir = os.path.join(self.install_path, LIBRARYNAME, 'Core')
        os.makedirs(spdir)

        statsdir = os.path.join(self.install_path, LIBRARYNAME, 'Core', 'Statistics')
        os.makedirs(statsdir)
        
        superpeerfilename = os.path.join(spdir, 'superpeer.txt')
        print >> sys.stderr,"test: writing empty superpeers to",superpeerfilename
        f = open(superpeerfilename, "w")
        f.write('# Leeg')
        f.close()

        self.config.set_install_dir(self.install_path)
        
        srcfiles = []
        srcfiles.append(os.path.join(LIBRARYNAME,"schema_sdb_v"+str(CURRENT_MAIN_DB_VERSION)+".sql"))
        for srcfile in srcfiles:
            sfn = os.path.join('..','..',srcfile)
            dfn = os.path.join(self.install_path,srcfile)
            print >>sys.stderr,"test: copying",sfn,dfn
            shutil.copyfile(sfn,dfn)

        

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


    def singtest_all_olproto_ver_current(self):
        self._test_all(OLPROTO_VER_CURRENT)

    def singtest_all_olproto_ver_11(self):
        self._test_all(11)

    def singtest_all_olproto_ver_8(self):
        self._test_all(8)

    def _test_all(self,myoversion):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # Arno, 2010-02-03: clicklog 1,2,3 must be run consecutively
        # create_mypref() must be called after clicklog 1,2,3
        self.subtest_good_buddycast_clicklog(1,myoversion)
        self.subtest_good_buddycast_clicklog(2,myoversion)
        self.subtest_good_buddycast_clicklog(3,myoversion)
        self.subtest_terms(myoversion)
        self.subtest_create_mypref()
        self.subtest_create_bc(myoversion)

    
    def get_good_clicklog_msg(self,n,myoversion=8):
        if n==1:
            # OLv8:
            # infohash
            # search terms
            # click position
            # reranking strategy
            # OLv11:
            # number of seeders
            # number of leechers
            # age of checking
            # number of sources seen'
            prec = ["hash1hash1hash1hash1", ["linux","ubuntu"], 1, 2]
            if myoversion >= 11:
                prec += [400, 500, 1000, 50]
            preferences = [prec]
            if myoversion >= 11:
                prec = ['hash0hash0hash0hash0', 300, 800, 5000, 30]
                collected_torrents = [prec]
            else:
                collected_torrents = ['hash0hash0hash0hash0'] 

        elif n==2:
            prec = ["hash2hash2hash2hash2", ["linux", "ubuntu"], 2, 2]
            if myoversion >= 11:
                prec += [600, 700,20000,60]
            preferences = [prec]
            if myoversion >= 11:
                prec = ['hash2hash2hash2hash2', 500, 200, 70000, 8000]
                collected_torrents = [prec]
            else:
                collected_torrents = ["hash2hash2hash2hash2"]            
        elif n==3:
            prec = ["hash3hash3hash3hash3", ["linux","redhat"], 5 ,2 ]
            if myoversion >= 11:
                prec += [800, 900, 30000, 70]
            preferences = [prec]
            if myoversion >= 11:
                prec = ['hash3hash3hash3hash3', 700, 200, 45000, 75]
                collected_torrents = [prec]
            else:
                collected_torrents = ['hash3hash3hash3hash3'] 

            
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
            

            
            
    def subtest_good_buddycast_clicklog(self, i, myoversion):
        """sends two buddy cast messages containing clicklog data,
           then checks in the DB to find out whether the correct
           data was stored.
           
           This in fact checks quite a lot of things.
           For example, the messages always contain terms [1,2]
        """
           
        print >>sys.stderr,"\ntest: subtest_good_buddycast_clicklog",i,"selversion",myoversion    
           
        s = OLConnection(self.my_keypair,'localhost',self.hisport,myoversion=myoversion)
        
        prefmsg = self.get_good_clicklog_msg(i,myoversion)
        
        print >>sys.stderr,myoversion,`prefmsg`
        
        msg = self.create_payload(prefmsg)
        s.send(msg)
        resp = s.recv()
        if len(resp)>0:
            print >>sys.stderr,"test: reply message %s:%s" % (getMessageName(resp[0]), resp[1:])
        else:
            print >>sys.stderr,"no reply message"
        self.assert_(len(resp) > 0)
            
        #if we have survived this, check if the content of the remote database is correct
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        term_db = self.session.open_dbhandler(NTFY_TERM)
        pref_db = self.session.open_dbhandler(NTFY_PREFERENCES)
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)

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
        

        # self.getAll("rowid, peer_id, torrent_id, click_position,reranking_strategy", order_by="peer_id, torrent_id")
        real_prefs = pref_db.getAllEntries()
        print >>sys.stderr,"test: getAllEntries returned",real_prefs
        
        my_peer_id = real_prefs[0][1] 
        real_terms = term_db.getAllEntries()
        real_search = search_db.getAllEntries()
        

        if i==1:
            wanted_prefs = [[1,my_peer_id,1,1,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu']]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1]]
        elif i==2:
            # Arno, 2010-02-04: Nicolas assumed the collected torrent for i=1
            # wouldn't be stored in DB?
            wanted_prefs = [[1,my_peer_id,'?',1,2],[2,my_peer_id,torrent_id,2,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu']]
            wanted_search = [[1,my_peer_id,'?',1,0],
                             [2,my_peer_id,'?',2,1],
                             [3,my_peer_id,'?',1,0],
                             [4,my_peer_id,'?',2,1]]
            
        elif i==3:
            wanted_prefs = [[1,my_peer_id,'?',1,2],[2,my_peer_id,'?',2,2],[3,my_peer_id,torrent_id,5,2]]
            wanted_terms = [[1,u'linux'], [2,u'ubuntu'], [3, u'redhat']]
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

        self.assert_(self.lol_equals(real_search, wanted_search, "good buddycast %d: search" % i))
        self.assert_(self.lol_equals(real_terms, wanted_terms, "good buddycast %d: terms" % i))
        self.assert_(self.lol_equals(real_prefs, wanted_prefs, "good buddycast %d: prefs" % i))
        
    def subtest_terms(self,myoversion):
        """assumes clicklog message 1 and 2 have been sent and digested"""
        
        print >>sys.stderr,"\ntest: subtest_terms"
        
        term_db = self.session.open_dbhandler(NTFY_TERM)
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport,myoversion=myoversion)        
        msg = self.get_good_clicklog_msg(3,myoversion)
        msg = self.create_payload(msg)
        s.send(msg)
        resp = s.recv()
        self.assert_(len(resp) > 0)
        
        termid = term_db.getTermID(u"linux")
        print >>sys.stderr, "TermID for Linux: %s" % termid
        #self.assert_(termid == 1)
        
        #self.assert_(term_db.getTerm(1)==bin2str(str(u"linux")))
        
        completedTerms = term_db.getTermsStartingWith("li")
        print >> sys.stderr, "terms starting with l: %s" % completedTerms  
        self.assert_(len(completedTerms)==1)
        self.assert_(u'linux' in completedTerms)
        
        term_db.insertTerm("asd#")
        completedTerms = term_db.getTermsStartingWith("asd")
        print >> sys.stderr, "terms starting with asd: %s" % completedTerms  
        self.assert_(len(completedTerms)==1)
        # Arno, 2010-02-03: Nicolas had 'asd' here, but I don't see any place
        # where the # should have been stripped.
        #
        self.assert_(u'asd#' in completedTerms)
        



    def subtest_create_mypref(self):
        print >>sys.stderr,"\ntest: creating test MyPreference data"
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db.addInfohash('mhashmhashmhashmhash')
        torrent_id = torrent_db.getTorrentID('mhashmhashmhashmhash')
        mypref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        
        mypref_db.addMyPreference('mhashmhashmhashmhash', {'destination_path':''}, commit=True)
        clicklog_data = {
                            'click_position': 1,
                            'reranking_strategy': 2,
                            'keywords': ['linux', 'fedora']
                        }
        mypref_db.addClicklogToMyPreference('mhashmhashmhashmhash', clicklog_data, commit=True)
        
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
        
        
    def subtest_create_bc(self,myoversion):
        print >>sys.stderr,"\ntest: creating test create_bc"
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        torrent_db._db.update("Torrent", status_id=1)
        pref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)
        pref_db.loadData()
        msg = self.buddycast.buddycast_core.createBuddyCastMessage(0, myoversion, target_ip="127.0.0.1", target_port=80)
        print >> sys.stderr, "created bc pref: %s" % msg
        
        wantpref = ['mhashmhashmhashmhash',['linux','fedora'],1,2]
        if myoversion >= OLPROTO_VER_ELEVENTH:
            wantpref += [-1,-1,-1,-1]  
        wantprefs = [wantpref]
                
        self.assert_(msg['preferences']==wantprefs)
        

                
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


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_buddycast_msg8plus.py <method name>"
    else:
        suite.addTest(TestBuddyCastMsg8Plus(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
