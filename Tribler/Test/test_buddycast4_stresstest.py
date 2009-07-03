# Written by Nicolas Neubauer, modified from test_bartercast.py
# see LICENSE.txt for license information

import random
import unittest
import os
import time as T
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.CacheDB.SqliteCacheDBHandler import *


def list_zipf_values(exponent, num_of_values):
    list_of_values = []
    b = 2 ** (exponent - 1)
    while len(list_of_values) < num_of_values:
        value = genvalue(b, exponent)
        if value != None:
            list_of_values.append(value)
        return list_of_values

def genvalue(b, exponent):
    U = random.uniform(0,1)
    V = random.uniform(0,1)
    X = math.floor(U ** (-(1/(exponent - 1))))
    T = (1 + (1/X)) ** (exponent - 1)
    upper_bound = T/b
    value = V*X*((T-1)/(b-1))
    if value <= upper_bound:
        return value


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

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        
        self.myhash = sha(self.mypermid).digest()
        
        self.buddycast = BuddyCastFactory.getInstance(superpeer=True)
        self.buddycast.olthread_register(True)
        
            
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
        self.queryfile = "c:\\files\\workspace\\python\\MyTribler\\Tribler\\queries.txt"
        self.queries = []
        f = open(self.queryfile,"r")
        oldline = ""
        for line in f.xreadlines():
            line = unicode(line[0:-1], 'Latin-1')
            if line==oldline:
                continue
            if line.strip=="":
                continue
            oldline= line
            self.queries.append(line)
            print repr(line)
            
        print "queries: %d" % len(self.queries)
        self.stresstest()
        
    def mean(self,l):
        return sum(l)/(0.0+len(l))

    def stresstest(self):
        search_db = self.session.open_dbhandler(NTFY_SEARCH)
        term_db = self.session.open_dbhandler(NTFY_TERM)
        pref_db = self.session.open_dbhandler(NTFY_PREFERENCES)        
        
        num_torrents = 250000
        num_peers = 65000
        num_torrents_per_user = 25
        query_ids = range(len(self.queries))
        queries_per_torrent = 10
        # set up a number of possible queries for each torrent
        print "setting up queries"
        torrent_terms = dict([(torrent_id, random.sample(query_ids, queries_per_torrent)) 
                              for torrent_id 
                              in xrange(num_torrents)])
        
        log= open("c:\\log.txt", "w")
        
        for peer_id in xrange(num_peers):
            store_times = []
            complete_times = []
            relterm_times = []
            
            if peer_id%10==0:
                print peer_id            
                log.flush()
                
            
            # put a slight long-tail distribution over torrents such that we get more frequently and less
            # frequently clicked torrents.
            # this causes the clicklo lookup distribution to spread in the graph 
            torrent_ids = [min(int(num_torrents*random.betavariate(1,.3)), num_torrents-1) 
                           for x 
                           in range(num_torrents_per_user)]
            
            query_ids = dict([ (torrent_id, random.choice(torrent_terms[torrent_id])) 
                                 for torrent_id 
                                 in torrent_ids])
            query_terms = dict([ (torrent_id, self.queries[query_id].replace(","," ").split(" ")) 
                                 for (torrent_id, query_id)
                                 in query_ids.items()])
            all_term_lists = query_terms.values()
            all_terms = []
            for term_list in all_term_lists:
                for term in term_list:
                    if not term in all_terms:
                        all_terms.append(term)
            #print all_terms
            before= T.time()
            term_db.bulkInsertTerms(all_terms)
            after = T.time()
            termtime = after-before             

            
            for torrent_id in torrent_ids:
                terms = query_terms[torrent_id]
                before = T.time() 
                try:
                    search_db.storeKeywords(peer_id, 
                                           torrent_id, 
                                           terms=terms, 
                                           commit=False)
                except:
                    print terms
                    raise
                after = T.time()
                store_times.append(after-before)

                    
            before=T.time()
            search_db.commit()
            after=T.time()
            commit_time = after-before

            for torrent_id in torrent_ids:
                for term in query_terms[torrent_id]:
                    if len(term)==0:
                        continue
                    before = T.time()
                    t = term_db.getTermsStartingWith(term[0])
                    after = T.time()
                    complete_times.append(after-before)
                    
                    before = T.time()
                    #print "torrent_id, term_id: %d, %d" % (term_db.getTermID(term), torrent_id)
                    A = search_db.getRelativeTermFrequency(term_db.getTermID(term), torrent_id)
                    #print A
                    after = T.time()
                    relterm_times.append(after-before)                                    
                    
            print "\n\n\nOVERALL: %f" % (termtime+sum(store_times)+commit_time)
            print "term time: %f" % termtime
            print "storage: %f (%f)" % (sum(store_times), self.mean(store_times))
            print "commit: %f" % commit_time
            print "completion: %f" % self.mean(complete_times)
            print "retrieval: %f" % self.mean(relterm_times)
            termsindb = term_db.getNumTerms()
            print "terms: %d" % termsindb
                      
            log.write("%d\t%f\t%f\t%f\t%f\t%f\t%f\t%d\n" % (peer_id,
                                                             termtime+sum(store_times)+commit_time,
                                                             termtime, 
                                                             sum(store_times),
                                                             commit_time, 
                                                             self.mean(complete_times), 
                                                             self.mean(relterm_times),
                                                             termsindb))
            

                
        log.close()            
                
            
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

