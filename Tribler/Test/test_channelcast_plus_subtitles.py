# Written by Andrea Reale
# see LICENSE.txt for license information


import unittest
from copy import deepcopy
from olconn import OLConnection
from Tribler.Core.API import *
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.BuddyCast.moderationcast_util import validChannelCastMsg
from Tribler.Core.BuddyCast.channelcast import ChannelCastCore
from Tribler.Test.test_channelcast import TestChannels
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
import os.path

DEBUG=True

RES_DIR = "subtitles_test_res"

class TestChannelsPlusSubtitles(TestChannels):
    """ 
    Testing the rich metadata extension of channelcast.
    
    The test suite defined in this module executes all the old 
    channelcast tests, plus a test to validate that the rich metadata
    (currently subtitles) extension works properly
    """


        
    def setupDB(self,nickname):
        TestChannels.setupDB(self,nickname)
        try:
            self.richMetadata_db = self.session.open_dbhandler(NTFY_RICH_METADATA)
            #add some metadata for torrents (they are defined in TestChannels.setupDB()
            self.mdto = MetadataDTO(self.hispermid, self.infohash1)
            subtitle1 = SubtitleInfo("nld", os.path.join(RES_DIR,"fake.srt"))
            subtitle1.computeChecksum()
            
            subtitle2 = SubtitleInfo("eng", os.path.join(RES_DIR, "fake0.srt"))
            subtitle2.computeChecksum()
            self.mdto.addSubtitle(subtitle1)
            self.mdto.addSubtitle(subtitle2)
            
            self.mdto.sign(self.his_keypair)
            
            self.richMetadata_db.insertMetadata(self.mdto)
        except:
            print_exc()
        
        
    def tearDown(self):
        TestChannels.tearDown(self)
        self.session.close_dbhandler(self.richMetadata_db)
        
    def _test_all(self,nickname):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        
        TestChannels._test_all(self,nickname)
        self.subtest_channelcastPlusMetadata()
        
      
    def subtest_channelcastPlusMetadata(self):
        '''
        Extends channelcast test to channelcast messages enriched with
        metadata (subtitles) informations
        '''
        print >>sys.stderr,"test: channelcast_subtitles ---------------------------"
        s = OLConnection(self.my_keypair,'localhost',self.hisport)
        chcast = ChannelCastCore(None, s, self.session, None, log = '', dnsindb = None)
        
        #test send standard channelcast
        chdata = {}
        print >> sys.stderr, "Test Good ChannelCast Plus Subtitles", `chdata`
        msg = CHANNELCAST+bencode(chdata)
        s.send(msg)
        resp = s.recv()
        if len(resp) > 0:
            print >>sys.stderr,"test: channelcast_subtitles: got",getMessageName(resp[0])
        self.assert_(resp[0]==CHANNELCAST)
        print >>sys.stderr, "test: channelcast_subtitles: got msg", `bdecode(resp[1:])`
        chdata_rcvd = bdecode(resp[1:])
        self.assertTrue(validChannelCastMsg(chdata_rcvd))
        
        for entry in chdata_rcvd.itervalues():
            if entry['infohash'] == self.infohash1: #the torrent for which two subtitles exist
                self.assertTrue('rich_metadata' in entry.keys())
                richMetadata = entry['rich_metadata']
                print >> sys.stderr, "test: channelcast_subtitles: richMetadata entry is ", richMetadata
                self.assertEquals(6, len(richMetadata))
                self.assertEquals(self.mdto.description, richMetadata[0])
                self.assertEquals(4, len(richMetadata[2])) #the subtitles mask 4 bytes
                self.assertTrue(isinstance(richMetadata[3],list)) #the subtitles checsums
                for checksum in richMetadata[3]:
                    self.assertEquals(20,len(checksum)) #160 bit sha1 checksum
                self.assertEquals(self.mdto.signature, richMetadata[4])
                self.assertEquals(4,len(richMetadata[5])) #the subtitles have mask 32 bit
                #also must (in this case) be equal to the subtitles mask
                self.assertEquals(richMetadata[2], richMetadata[5])
                
                print >> sys.stderr, "test: channelcast_subtitles; richMetadata entry is valid and correct"
            else:
                self.assertFalse('rich_metadata' in entry.keys())
                
        s.close()
        
        #Now, send a bad ChannelCast message.
        # The other side should close the connection
        # Create bad message by manipulating a good one
        #bad bitmask
        chdata = deepcopy(chdata_rcvd)
        for k,v in chdata.items():
            if 'rich_metadata' in v:
                v['rich_metadata'][2] = 44 #an integer instead of a 4bytes bitmask
        self.subtest_bad_channelcast(chdata)
    
                
        #Bad message format
        chdata = deepcopy(chdata_rcvd)
        for k,v in chdata.items():
            if 'rich_metadata' in v:
                v['rich_metadata'].insert(0, u"asdfafa22")
        self.subtest_bad_channelcast(chdata)
        
        #Bad 
        print>>sys.stderr, "End of channelcast_subtitles test ---------------------------"
    
            


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. PeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_channelcast_plus_subtitles.py <method name>"
    else:
        suite.addTest(TestChannelsPlusSubtitles(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])

if __name__ == "__main__":
    main()
