import unittest
import os
import sys
import time
import socket
from sha import sha
from random import randint,shuffle
from traceback import print_exc
from types import StringType, ListType, DictType, IntType, BooleanType
from time import sleep, time

import tempfile
from M2Crypto import Rand,EC

from Tribler.Test.test_as_server import TestAsServer
from Tribler.Core.Session import *
from olconn import OLConnection
import btconn
from Tribler.Core.BuddyCast.channelcast import ChannelCastCore
from Tribler.Core.BuddyCast.votecast import VoteCastCore
from Tribler.Core.SocialNetwork.ChannelQueryMsgHandler import ChannelQueryMsgHandler
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.simpledefs import *
from Tribler.Core.CacheDB.CacheDBHandler import *
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.Overlay.permid import sign_data, generate_keypair, permid_for_user
import os
import sys
import time
DEBUG=True

class FakeLaunchmany:
    
    def __init__(self):
        self.peer_db = PeerDBHandler.getInstance()
        self.superpeer_db = SuperPeerDBHandler.getInstance()
        self.torrent_db = TorrentDBHandler.getInstance()
        self.mypref_db = MyPreferenceDBHandler.getInstance()
        self.pref_db = PreferenceDBHandler.getInstance()
        self.friend_db =  FriendDBHandler.getInstance()
        self.listen_port = 6881
        self.session = Session()

    def get_ext_ip(self):
        return '127.0.0.1'

class FakeOverlayBridge:
    def add_task(self, foo, sec=0):
        foo()

class TestChannelCast(TestAsServer):
    """   Testing ChannelCast message    """
    
    
    def setUp(self):
        """ override TestAsServer """
        # From TestAsServer.setUp(self): ignore singleton on
        self.setUpPreSession()
        self.session = Session(self.config,ignore_singleton=True)
        self.hisport = self.session.get_listen_port()        
        self.setUpPostSession()

        # New code
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.channelcastdb.registerSession(self.session) 
        
        self.votecastdb = VoteCastDBHandler.getInstance()
        self.votecastdb.registerSession(self.session)       

    def setUpPreSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPreSession(self)
        # BuddyCast
        self.config.set_buddycast(True)
        self.config.set_start_recommender(True)
        
        fd,self.superpeerfilename = tempfile.mkstemp()
        os.write(fd,'')
        os.close(fd)
        self.config.set_superpeer_file(self.superpeerfilename)

    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)

        self.mypermid = str(self.my_keypair.pub().get_der())
        self.hispermid = str(self.his_keypair.pub().get_der())        
        self.myhash = sha(self.mypermid).digest()
        
        
    def tearDown(self):
        """ override TestAsServer """
        TestAsServer.tearDown(self)
        try:
            os.remove(self.superpeerfilename)
        except:
            print_exc()

    def test_channel_subscription(self):
        self.votecastdb.unsubscribe(bin2str(self.mypermid))
        self.assertEqual(self.votecastdb.getVote(bin2str(self.mypermid),bin2str(self.hispermid)),None)
        print >> sys.stderr, self.votecastdb.getAll()

        self.votecastdb.spam(bin2str(self.mypermid))
        self.assertEqual(self.votecastdb.getVote(bin2str(self.mypermid),bin2str(self.hispermid)),-1)
        print >> sys.stderr, self.votecastdb.getAll()
                
        self.votecastdb.subscribe(bin2str(self.mypermid))
        self.assertEqual(self.votecastdb.getVote(bin2str(self.mypermid),bin2str(self.hispermid)),2)
        print >> sys.stderr, self.votecastdb.getAll()
        
        self.votecastdb.unsubscribe(bin2str(self.mypermid))
        self.assertEqual(self.votecastdb.getVote(bin2str(self.mypermid),bin2str(self.hispermid)),0)
        print >> sys.stderr, self.votecastdb.getAll()
        
        self.votecastdb.spam(bin2str(self.mypermid))
        self.assertEqual(self.votecastdb.getVote(bin2str(self.mypermid),bin2str(self.hispermid)),-1)
        print >> sys.stderr, self.votecastdb.getAll()
        
    def check_chquery_reply(self,data):
        d = bdecode(data)
        self.assert_(type(d) == DictType)
        self.assert_(d.has_key('a'))
        self.assert_(d.has_key('id'))
        id = d['id']
        self.assert_(type(id) == StringType)                

    def test_channelcast(self):
        torrent_data = {'announce':"http://localhost", 'info':{'name':'Hello 123', 'files':[{'length':100, 'path':['license.txt']}]}}
        infohash = bin2str(sha(bencode(torrent_data['info'])).digest())
        self.channelcastdb.addOwnTorrent(infohash,torrent_data)
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        chcast = ChannelCastCore(None, s, self.session, None, log = '', dnsindb = None)
        
        # Good message
        chdata =  chcast.createChannelCastMessage()
        if chdata is None or len(chdata) ==0:
            print "test: no subscriptions for us.. hence do not send"       
        else:
            msg = CHANNELCAST + bencode(chdata)        
            print "test: channelcast msg created", repr(chdata)        
            s.send(msg)
        
        time.sleep(3)
        
        # Bad message
        if chdata is None or len(chdata)==0:
            pass
        else:
            pub_id, pub_name, infohash, torrenthash, name, timestamp, signature = chdata[0]
            chdata = [(pub_id, pub_name, infohash, torrenthash, name, 12343, signature)]
            msg = CHANNELCAST + bencode(chdata)        
            print "test: channelcast msg created", repr(chdata)        
            s.send(msg)
            time.sleep(20)
            # the other side should have closed the connection, as it is invalid message
        
            
        s.close()        
        
    def test_channel_query(self):
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = CHANNEL_QUERY+bencode({'q':'k:dutiet', 'id': 'a' * 20})
        s.send(msg)
        resp = s.recv()
        if len(resp) > 0:
            print >>sys.stderr,"test: good CH_QUERY: got",getMessageName(resp[0])
            self.assert_(resp[0] == CHANNEL_QUERY_REPLY)
            self.check_chquery_reply(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        #s.send('bla')
        s.close()        
    
    def test_channel_update(self):
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        msg = CHANNEL_QUERY+bencode({'q':'p:345fsdf34fe345ed344g5', 'id': 'a' * 20})
        s.send(msg)
        resp = s.recv()
        if len(resp) > 0:
            print >>sys.stderr,"test: good CH_QUERY: got",getMessageName(resp[0])
            self.assert_(resp[0] == CHANNEL_QUERY_REPLY)
            self.check_chquery_reply(resp[1:])
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()
            
    def test_votecast(self):
        self.votecastdb.subscribe('nitin')
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        votecast = VoteCastCore(None, s, self.session, None, log = '', dnsindb = None)
        data = votecast.createVoteCastMessage()
        if data is None and len(data)==0:
            print >>sys.stderr, "test: no votes"
        else:
            msg = VOTECAST + bencode(data)
            s.send(msg)
            s.close()
            
        

def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_channelcast.py <method name>"
    else:
        suite.addTest(TestChannelCast(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()

def usercallback(permid,query,d):
    print >> sys.stderr, "chquery_connected_peers: Processing reply:", permid, query, repr(d)