# Written by Andrea Reale
# see LICENSE.txt for license information


import unittest
import logging
from Tribler.Core.Overlay.permid import generate_keypair, sign_data
from random import randint
import hashlib
import time
from Tribler.Core.Utilities.bencode import bencode
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.Subtitles.RichMetadataInterceptor import RichMetadataInterceptor
from Tribler.Test.Core.Subtitles.simple_mocks import MockMetadataDBHandler,\
    MockSubtitlesHandler, MockVoteCastHandler, MockPeersHaveMngr


logging.basicConfig(level=logging.DEBUG)


CHANNELCAST_NUM_OF_ENTRIES = 2





class TestRichMetadataInterceptor(unittest.TestCase):




    def setUp(self):

        self.metadataDBHandler = MockMetadataDBHandler()
        self.voteCastDBHandler = MockVoteCastHandler()
        self.subSupp = MockSubtitlesHandler()
        self.my_permid_and_keypair = generatePermIds(1)[0]
        self.advertisedChannelIds = generatePermIds(CHANNELCAST_NUM_OF_ENTRIES)
        self.advertisedInfohash =  generateInfohashes(CHANNELCAST_NUM_OF_ENTRIES)
        self.peersHaveMngr = MockPeersHaveMngr()

        self.channelcastMsg = dict()
        for i in range(CHANNELCAST_NUM_OF_ENTRIES):

            signature, msg = generateChannelCastEntry(self.advertisedChannelIds[i][0],
                                                      self.advertisedInfohash[i],
                                                      self.advertisedChannelIds[i][1])

            self.channelcastMsg[signature] = msg

        self.undertest = RichMetadataInterceptor(self.metadataDBHandler, self.voteCastDBHandler,
                                                 self.my_permid_and_keypair[0], self.subSupp,
                                                 self.peersHaveMngr)

        self.metadataDBHandler.nextKeypair = self.advertisedChannelIds[0][1]



    def testAddRMDContentNoContent(self):
        self.metadataDBHandler.returnMetadata = False
        newMessage = self.undertest.addRichMetadataContent(self.channelcastMsg)
        #message should be left untouched
        self.assertEquals(self.channelcastMsg,newMessage)
        #check if the the db handler is called
        self.assertEquals(CHANNELCAST_NUM_OF_ENTRIES,self.metadataDBHandler.getMetadataCount)

        for i in range(CHANNELCAST_NUM_OF_ENTRIES):
            self.assertTrue(
                            (self.advertisedChannelIds[i][0], self.advertisedInfohash[i])
                              in self.metadataDBHandler.getMetadataParametesHistory)

    def testAddRichMetadataContentSomeContent(self):
        self.metadataDBHandler.returnMetadata = True
        newMessage = self.undertest.addRichMetadataContent(self.channelcastMsg)
        #message should have been changed
        self.assertNotEquals(self.channelcastMsg,newMessage)

        for item in newMessage.itervalues():
            #check the contents of the modified message
            self.assertTrue('rich_metadata' in item.keys())
            #description,bitmask,timestamp,listofchecksums, signature
            self.assertEquals(6, len(item['rich_metadata']))






    def test_splitChnAndRmdNoContent(self):
        self.metadataDBHandler.returnMetadata = False
        newMessage = self.undertest.addRichMetadataContent(self.channelcastMsg)

        listOfmetadata = \
            self.undertest._splitChannelcastAndRichMetadataContents(newMessage)

        self.assertEquals(([],[]),listOfmetadata)


    def test_splitChnAndRmdSomeContent(self):
        self.metadataDBHandler.returnMetadata = True
        newMessage = self.undertest.addRichMetadataContent(self.channelcastMsg)

        listOfmetadata = \
            self.undertest._splitChannelcastAndRichMetadataContents(newMessage)

        listOfmetadata = listOfmetadata[0]
        self.assertEquals(2,len(listOfmetadata))
        for dto in listOfmetadata:
            self.assertTrue(isinstance(dto[0], MetadataDTO))

    def testHandleRMetadata(self):
        self.metadataDBHandler.returnMetadata = True
        newMessage = self.undertest.addRichMetadataContent(self.channelcastMsg)

        #it will result that i am a subscriber for any channel
        self.voteCastDBHandler.nextVoteValue = 2


        self.undertest.handleRMetadata(self.advertisedChannelIds[0][0],
                                       newMessage)

        self.assertEquals(2, self.metadataDBHandler.insertMetadataCount)
        self.assertEquals(2, self.subSupp.retrieveMultipleCount)

        pass






def generatePermIds(numOfPermids):
    permids = list()
    keypair = generate_keypair()

    #two equal permids for ease of testing
    permids.append((str(keypair.pub().get_der()), keypair))
    permids.append((str(keypair.pub().get_der()), keypair))
#    for i in range(numOfPermids):
#        keypair = generate_keypair()
#        permids.append((str(keypair.pub().get_der()), keypair))
    return permids

def generateInfohashes(num):
    infohashes = list()
    hasher = hashlib.sha1()
    for i in range(num):
        seed = randint(0,1000)
        hasher.update(str(seed))
        infohash = hasher.digest()
        infohashes.append(infohash)

    return infohashes

def generateChannelCastEntry(channel, infohash, keypair):
    channel_name = u'channel-' + unichr(randint(0,255))
    torrent_name = u'torrent-' + unichr(randint(0,255))
    timestamp = int(time.time())
    msg = dict()
    msg['publisher_id'] = str(channel)
    msg['publisher_name'] = channel_name
    msg['infohash'] = str(infohash)
    msg['torrentname'] = torrent_name
    msg['timestamp'] = timestamp

    bencoded = bencode(msg)

    signature = sign_data(bencoded, keypair)

    return signature, msg



def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestRichMetadataInterceptor)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
