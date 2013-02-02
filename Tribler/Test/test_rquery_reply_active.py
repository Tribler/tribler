# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import sys
import time
from time import sleep
from types import StringType, DictType

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.MessageID import QUERY, QUERY_REPLY, getMessageName

from olconn import OLConnection
from Tribler.Test.test_as_server import TestAsServer

DEBUG=True

LENGTH = 481
LEECHERS = 22
SEEDERS = 11
CATEGORY = ' Video'

class TestQueryReplyActive(TestAsServer):

    """  
    Testing QUERY_REPLY message of Query extension V1 

    This test checks how the Tribler code responds to good and bad 
    QUERY_REPLY messages. I.e. the Tribler client initiates
    the dialback by connecting to us and sending a QUERY and we
    reply with good and bad messages.

    This test allows authoritative answers from superpeers.

    WARNING: Each of the test_ methods should be tested by running the TestCase 
    in a separate Python interpreter to prevent problems with our singleton 
    classes, e.g. SuperPeerDB, etc.
    """

    def setUpPreSession(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: Pre Tribler Init"
        TestAsServer.setUpPreSession(self)
        print >> sys.stderr,"test: Pre Tribler Init: config_path",self.config_path
        # Enable remote querying
        self.config.set_remote_query(True)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)
        self.hispermid = str(self.his_keypair.pub().get_der())
        self.my_permid = str(self.my_keypair.pub().get_der())

    def pretest_simple(self,keyword):
        self.pretest_q('SIMPLE',keyword)

    def pretest_simpleplustorrents(self,keyword):
        self.pretest_q('SIMPLE+METADATA',keyword)

    def pretest_q(self,queryprefix,keyword):
        
        query = queryprefix+' '+keyword
        
        self.content_name = keyword.upper()+' S22E44'
        self.tdef = TorrentDef()
        self.tdef.set_tracker('http://localhost:0/announce')
        self.tdef.set_piece_length(2 ** 15)
        self.tdef.create_live(self.content_name,2 ** 16)
        self.tdef.finalize()
        
        # 1. First connect to Tribler
        self.openconn = OLConnection(self.my_keypair,'localhost',self.hisport)
        sleep(3)
        
        # 2. Make Tribler send query
        self.query = query
        self.session.query_connected_peers(query,self.query_usercallback,max_peers_to_query=10)

    def query_usercallback(self,permid,query,hits):
        
        print >>sys.stderr,"test: query_usercallback:",`permid`,`query`,`hits`
        
        self.assert_(query == self.query)
        self.assert_(permid == self.my_permid)
        self.check_good_qreply(hits)
        
        # TODO: if SIMPLE+METADATA: check torrent now in db.
        

    #
    # Good SIMPLE QUERY, builds on TestQueryReply code
    #    
    def singtest_good_simple_reply(self):
        self.pretest_simple('hallo')
        self._test_qreply(self.create_good_simple_reply,True)

    #
    # Good SIMPLE+METADATA QUERY, builds on TestQueryReply code
    #    
    def singtest_good_simpleplustorrents_reply(self):
        self.pretest_simpleplustorrents('hallo')
        self._test_qreply(self.create_good_simpleplustorrents_reply,True)


    #
    # Good SIMPLE QUERY Unicode, builds on TestQueryReply code
    #    
    def singtest_good_simple_reply_unicode(self):
        self.pretest_simple(u'Ch\u00e8rie')
        self._test_qreply(self.create_good_simple_reply,True)

    #
    # Good SIMPLE+METADATA QUERY Unicode, builds on TestQueryReply code
    #    
    def singtest_good_simpleplustorrents_reply_unicode(self):
        self.pretest_simpleplustorrents(u'Ch\u00e8rie')
        self._test_qreply(self.create_good_simpleplustorrents_reply,True)


    #
    # Bad QUERY, builds on TestQueryReply code
    #    
    def singtest_bad_not_bdecodable(self):
        self.pretest_simple('hallo')
        self._test_qreply(self.create_not_bdecodable,False)

    #
    # Bad SIMPLE+METADATA QUERY, builds on TestQueryReply code
    #    
    def singtest_bad_not_bdecodable_torrentfile(self):
        self.pretest_simpleplustorrents('hallo')
        self._test_qreply(self.create_not_bdecodable_torrentfile,False)


    ### TODO: send different valid answers so consensus not reached

    #
    # Main test code
    #
    def _test_qreply(self,gen_qreply,good):
        print >> sys.stderr,"test: waiting for reply"
        s = self.openconn

        msg = s.recv()
        self.assert_(len(msg) > 0)
        print >> sys.stderr,"test: Received overlay message",getMessageName(msg[0])
        self.assert_(msg[0] == QUERY)
        id = self.check_rquery(msg[1:])
        
        resp = gen_qreply(id)
        print >> sys.stderr,"test: sending QUERY_REPLY"
        s.send(resp)
        if good:
            time.sleep(10)
            # the other side should not have closed the connection, as
            # this is all valid, so this should not throw an exception:
            s.send('bla')
            s.close()
        else:
            # the other side should not like this and close the connection
            self.assert_(len(s.recv())==0)
            s.close()


    def create_good_simple_reply_dict(self,id):
        r = {}
        r['content_name'] = self.content_name.encode("UTF-8")
        r['length'] = LENGTH
        r['leecher'] = LEECHERS
        r['seeder'] = SEEDERS
        r['category'] = CATEGORY
        # OLPROTO_PROTO_ELEVENTH
        # set later r['torrent_size'] = 42
        r['channel_permid'] = '$' * 83
        r['channel_name'] = 'Nitin Channel' 
        
        d2 = {}
        d2[self.tdef.get_infohash()] = r
        
        d = {}
        d['id'] = id
        d['a'] = d2
        return d
        
    def create_good_simple_reply(self,id):
        d = self.create_good_simple_reply_dict(id)
        bmetainfo = bencode(self.tdef.get_metainfo())
        d['a'][self.tdef.get_infohash()]['torrent_size'] = len(bmetainfo) 
        b = bencode(d)
        return QUERY_REPLY+b

    def create_good_simpleplustorrents_reply(self,id):
        d = self.create_good_simple_reply_dict(id)
        bmetainfo = bencode(self.tdef.get_metainfo())
        d['a'][self.tdef.get_infohash()]['torrent_size'] = len(bmetainfo)
        d['a'][self.tdef.get_infohash()]['metatype'] = 'application/x-tribler-stream' 
        d['a'][self.tdef.get_infohash()]['metadata'] = bmetainfo 
        b = bencode(d)
        return QUERY_REPLY+b

    

    def check_good_qreply(self,hits):
        self.assert_(len(hits) == 1)
        self.assert_(hits.keys()[0] == self.tdef.get_infohash())
        hit = hits[self.tdef.get_infohash()]
        self.assert_(hit['content_name'] == self.content_name)
        self.assert_(hit['length'] == LENGTH)
        self.assert_(hit['leecher'] == LEECHERS)
        self.assert_(hit['seeder'] == SEEDERS)
        self.assert_(hit['category'] ==  CATEGORY)
    
        # OLPROTO_VERSION_ELEVENTH
        bmetainfo = bencode(self.tdef.get_metainfo())
        self.assert_(hit['torrent_size'] == len(bmetainfo))
        if self.query.startswith('SIMPLE+METADATA'):
            self.assert_(hit['metadata'] == bmetainfo)

    def create_not_bdecodable(self,id):
        return QUERY_REPLY+"bla"

    def create_not_bdecodable_torrentfile(self,id):
        d = self.create_good_simple_reply_dict(id)
        d['a'][self.tdef.get_infohash()]['torrent_size'] = 3 # consistent with metadata. Should be named "metasize"
        d['a'][self.tdef.get_infohash()]['metadata'] = 'bla'
        b = bencode(d)
        return QUERY_REPLY+b

    def check_rquery(self,data):
        d = bdecode(data)
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('q'))
        q = d['q']
        self.assert_(type(q) == StringType)
        self.assert_(d.has_key('id'))
        id = d['id']
        self.assert_(type(id) == StringType)

        self.assert_(q == self.query.encode("UTF-8"))
        return d['id']


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. SuperPeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_rquery_active_reply.py <method name>"
    else:
        suite.addTest(TestQueryReplyActive(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])
    
if __name__ == "__main__":
    main()
