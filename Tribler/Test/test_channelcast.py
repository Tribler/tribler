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
from olconn import OLConnection
import btconn
from Tribler.Core.BuddyCast.channelcast import ChannelCastCore
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.simpledefs import *
from Tribler.Core.CacheDB.CacheDBHandler import ChannelCastDBHandler
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB, bin2str, str2bin, NULL
from Tribler.Core.Overlay.permid import sign_data, generate_keypair, permid_for_user
import os
import sys
import time
DEBUG=True


class TestChannelCast(TestAsServer):
    """   Testing ModerationCast message    """
    
    
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
            
    def createSubscriptions(self):
        subs = {}
        for i in range(10):
            sleep(1)
            subs['publisher_id']='nitin' + str(i)
            subs['subscriber_id']= permid_for_user(self.mypermid)
            subs['time_stamp'] = int(time())        
            self.channelcastdb.addSubscription(subs)
    
    
    def test_subscribe(self):
        
        subs ={}
        subs['publisher_id']='nitin'
        subs['subscriber_id']= permid_for_user(self.mypermid)
        subs['time_stamp'] = 123123123      
        
        self.assertFalse(self.channelcastdb.hasSubscription(subs))
        
        self.channelcastdb.addSubscription(subs)
        
        print >> sys.stderr, "Test_Subscribe starts"
        self.assertTrue(self.channelcastdb.hasSubscription(subs))
        print >> sys.stderr, "Test_Subscribe: sub insertion checked"
        
        
        subs['publisher_id']=None
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but its NULL")
            print >> sys.stderr, "Test_Subscribe: Fails: Added Subscription but its NULL"
        except:
            print >> sys.stderr, "Test_Subscribe: pub"
            pass
        
        subs['subscriber_id']=None
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but its NULL")
            print >> sys.stderr, "Test_Subscribe: Fails: Added Subscription but its NULL"
        except:
            print >> sys.stderr, "Test_Subscribe: sub"
            pass
        
        subs['time_stamp']=None
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but its NULL")
            print >> sys.stderr, "Test_Subscribe: Fails: Added Subscription but its NULL"
        except:
            print >> sys.stderr, "Test_Subscribe: time_stamp"
            pass
        
        subs['publisher_id']= ''
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but pub is empty")
            print >> sys.stderr, "Test_Subscribe: pub empty"
        except:
            pass
        
        subs['subscriber_id']=None
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but sub is empty")
            print >> sys.stderr, "Test_Subscribe: sub empty"
        except:
            pass

        subs['time_stamp']= 'hee'
        try:
            self.channelcastdb.addSubscription(subs)
            self.fail("Fails: Added Subscription but its NULL")
            print >> sys.stderr, "Test_Subscribe: time diff"
        except:
            pass        
                 
    def test_unsubscribe(self):        
        subs ={}
        subs['publisher_id']='nitin'
        subs['subscriber_id']= permid_for_user(self.hispermid) # testbed holder's permid is in session, ie, session.permid = hispermid
        subs['time_stamp'] = 123123123      
        self.channelcastdb.addSubscription(subs)

        self.channelcastdb.removePublisher('nitin')
                
        self.assertFalse(self.channelcastdb.hasSubscription(subs))
        
        self.channelcastdb.removePublisher('nitin')
        print >> sys.stderr, "Removed nitin again!"
        
        self.channelcastdb.removePublisher(None)

    def test_channelcast(self):
        subs ={}
        subs['publisher_id']='nitin'
        subs['subscriber_id']= permid_for_user(self.hispermid) # testbed holder's permid is in session, ie, session.permid = hispermid
        subs['time_stamp'] = 12312323      
        self.channelcastdb.addSubscription(subs)
        
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        chcast = ChannelCastCore(None, s, self.session, None, log = '', dnsindb = None)
        chdata =  chcast.createChannelCastMessage()
        if chdata is None or len(chdata) ==0:
            print >>sys.stderr,"test: no subscriptions for us.. hence do not send"       
        else:
            msg = CHANNELCAST + bencode(chdata)        
            print >>sys.stderr,"test: channelcast msg created", repr(msg)        
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

