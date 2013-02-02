# Written by Andrea Reale
# see LICENSE.txt for license information

import unittest
import logging
import time
from struct import pack
from Tribler.Core.Subtitles.SubtitleHandler.SubsMessageHandler import SubsMessageHandler
from Tribler.Test.Core.Subtitles.simple_mocks import MockOverlayBridge, MockTokenBucket, MockMsgListener
from Tribler.Core.Overlay.permid import generate_keypair
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import LanguagesProvider
from Tribler.Core.MessageID import GET_SUBS, SUBS
from Tribler.Core.Utilities.bencode import bencode, bdecode
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FOURTEENTH


logging.basicConfig(level=logging.DEBUG)
_keypairs = (generate_keypair(), generate_keypair(), generate_keypair())
testChannelId = str(_keypairs[0].pub().get_der())
testDestPermId = str(_keypairs[1].pub().get_der())
testMyPermId = str(_keypairs[2].pub().get_der())

testInfohash = sha("yoman!").digest()

class TestSubtitlesMsgHandlerIsolation(unittest.TestCase):
    
    def setUp(self):
        self.ol_bridge = MockOverlayBridge()
        self.tokenBucket = MockTokenBucket()
        self.underTest = SubsMessageHandler(self.ol_bridge,self.tokenBucket,1000000)
        
    def test_addToRequestedSubtitles(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        bitmask1 = langUtil.langCodesToMask(["nld"])
        
        self.underTest._addToRequestedSubtitles(testChannelId,
                                                testInfohash, bitmask1)
        
        key = "".join((testChannelId, testInfohash))
        self.assertEquals(bitmask1,
                          self.underTest.requestedSubtitles[
                                                            key
                                                            ].cumulativeBitmask)
        
        bitmask2 = langUtil.langCodesToMask(["jpn", "ita"])
        self.underTest._addToRequestedSubtitles(testChannelId,
                                                testInfohash, bitmask2)
        
        self.assertEquals(bitmask1 | bitmask2,
                          self.underTest.requestedSubtitles[
                                                            key
                                                            ].cumulativeBitmask)
        
        removeBitmask = langUtil.langCodesToMask(["nld", "ita"])
        self.underTest._removeFromRequestedSubtitles(testChannelId,
                                                       testInfohash,
                                                       removeBitmask)
        
        codes = langUtil.maskToLangCodes(self.underTest.requestedSubtitles[
                                                            key
                                                            ].cumulativeBitmask)
        
        self.assertEquals(["jpn"], codes)
        
    def testSendSubtitlesRequestConnected(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        request = {}
        request['channel_id'] = testChannelId
        request['infohash'] = testInfohash
        request['languages'] = ["kor"]
        self.underTest.sendSubtitleRequest(testDestPermId, request, None, None, OLPROTO_VER_FOURTEENTH)
        
        self.assertEquals(0, self.ol_bridge.connect_count) #selversion was 1
        self.assertEquals(1, self.ol_bridge.send_count) #send called one time 
        
        binaryBitmask = pack("!L", langUtil.langCodesToMask(["kor"]))
        expectedMsg = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
        passedParameters = self.ol_bridge.sendParametersHistory[0]
        self.assertEquals(testDestPermId, passedParameters[0])
        self.assertEquals(expectedMsg, passedParameters[1])
        
    def testSendSubtitlesRequestNotConnected(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        
        request = {}
        request['channel_id'] = testChannelId
        request['infohash'] = testInfohash
        request['languages'] = ["kor"]
        
        self.underTest.sendSubtitleRequest(testDestPermId, request)
        
        self.assertEquals(1, self.ol_bridge.connect_count) #selversion was -1

        self.assertEquals(1, self.ol_bridge.send_count) #send called one time 
        
        binaryBitmask = pack("!L", langUtil.langCodesToMask(["kor"]))
        expectedMsg = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
        passedParameters = self.ol_bridge.sendParametersHistory[0]
        self.assertEquals(testDestPermId, passedParameters[0])
        self.assertEquals(expectedMsg, passedParameters[1])
        
        
    def test_decodeGETSUBSMessage(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        binaryBitmask = pack("!L", langUtil.langCodesToMask(["kor", "spa"]))
        
        bencodedMessage = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
        channel_id, infohash, languages = \
            self.underTest._decodeGETSUBSMessage(bencodedMessage)
            
        self.assertEquals(testChannelId, channel_id)
        self.assertEquals(testInfohash, infohash)
        self.assertEquals(["kor", "spa"], languages)
        
    def test_decodeGETSUBSMessageInvalid(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        
        binaryBitmask = pack("!L", langUtil.langCodesToMask(["kor", "spa"]))
        invalidTypeMsg = chr(25) + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
        
        self.assertRaises(AssertionError, self.underTest._decodeGETSUBSMessage,
                           (invalidTypeMsg,))
        
        invalidMsgField = GET_SUBS + \
                         bencode((
                              42,
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
              
        decoded = \
            self.underTest._decodeGETSUBSMessage(invalidMsgField)
        #when something in the body is wrong returns None
        self.assertTrue(decoded is None)
        
        invalidBitamsk = "\xff\xff\xff\xff\xbb"
        invalidMsgField = GET_SUBS + \
                         bencode((
                              testChannelId,
                              testInfohash,
                              invalidBitamsk #40 bit bitmask!)
                              ))
        
        decoded = \
            self.underTest._decodeGETSUBSMessage(invalidMsgField)
            
        #when something in the body is wrong returns None
        self.assertTrue(decoded is None)
        
            
    def test_createSingleResponseMessage(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        data = {
                'permid' : testDestPermId,
                'channel_id' : testChannelId,
                'infohash' : testInfohash,
                'subtitles' : {"eng" : "This is content 1", "nld": "This is content  2",
                               "ita" : "This is content 3"},
                'selversion' : OLPROTO_VER_FOURTEENTH
                }
        langs = data['subtitles'].keys()
        
        bitmask = langUtil.langCodesToMask(langs)
        binaryBitmask = pack("!L", bitmask)
        expextedMessage = SUBS + \
                            bencode((
                                    data['channel_id'],
                                    data['infohash'],
                                    binaryBitmask,
                                    [data['subtitles']['eng'], data['subtitles']['ita'],
                                     data['subtitles']['nld']]
                                     ))
        msg = self.underTest._createSingleResponseMessage(data)
        decoded = bdecode(msg[1:])
        
        self.assertEquals(expextedMessage, msg)
        
        
            
    def test_receivedGETSUBSSimple(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        bitmask = langUtil.langCodesToMask(["eng", "rus"])
        binaryBitmask = pack("!L", bitmask)
        request = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              binaryBitmask
                              ))
        
        
        
        list = MockMsgListener()
        
        self.underTest.registerListener(list)
        self.underTest.handleMessage(testDestPermId, OLPROTO_VER_FOURTEENTH, request)
        
        self.assertEquals(1,list.receivedCount)
        self.assertEquals(testDestPermId, list.receivedParams[0][0])
        self.assertEquals(OLPROTO_VER_FOURTEENTH,list.receivedParams[0][2])
        self.assertEquals((testChannelId,testInfohash,["eng","rus"]),list.receivedParams[0][1])
        
    def test_receivedGETSUBSInvalid1(self):
        bitmask = -1
        request = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              bitmask
                              ))
        
        
        
        list = MockMsgListener()
        
        self.underTest.registerListener(list)
        val = self.underTest.handleMessage(testDestPermId, OLPROTO_VER_FOURTEENTH, request)
        
        self.assertFalse(val)
        self.assertEquals(0,list.receivedCount) #the invalid msg has been dropped
        
    def test_receivedGETSUBSInvalid2(self):
        bitmask = -1
        request = GET_SUBS + \
                      bencode((
                              testChannelId,
                              testInfohash,
                              bitmask
                              ))
        
        
        
        list = MockMsgListener()
        
        self.underTest.registerListener(list)
        val = self.underTest.handleMessage(testDestPermId, 13,request)
        
        self.assertFalse(val)
        self.assertEquals(0,list.receivedCount) #the invalid msg has been dropped
        
    def test_receivedSUBSSimpleNoRequest(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        data = {
                'permid' : testDestPermId,
                'channel_id' : testChannelId,
                'infohash' : testInfohash,
                'subtitles' : {"eng" : "This is content 1", "nld": "This is content  2",
                               "ita" : "This is content 3"},
                'selversion' : OLPROTO_VER_FOURTEENTH
                }
        langs = data['subtitles'].keys()
        
        bitmask = langUtil.langCodesToMask(langs)
        binaryBitmask = pack("!L", bitmask)
        expextedMessage = SUBS + \
                            bencode((
                                    data['channel_id'],
                                    data['infohash'],
                                    binaryBitmask,
                                    [data['subtitles']['eng'], data['subtitles']['ita'],
                                     data['subtitles']['nld']]
                                     ))
        
        list = MockMsgListener()
        self.underTest.registerListener(list)                    
        val = self.underTest.handleMessage(testDestPermId, OLPROTO_VER_FOURTEENTH, expextedMessage)
        # never had a request for this message should be dropped
        self.assertFalse(val)
        self.assertEquals(0,list.subsCount)
        
    def test_receivedSUBSOtherRequest(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        data = {
                'permid' : testDestPermId,
                'channel_id' : testChannelId,
                'infohash' : testInfohash,
                'subtitles' : {"eng" : "This is content 1", "nld": "This is content  2",
                               "ita" : "This is content 3"},
                'selversion' : OLPROTO_VER_FOURTEENTH
                }
        langs = data['subtitles'].keys()
        
        bitmask = langUtil.langCodesToMask(langs)
        binaryBitmask = pack("!L", bitmask)
        expextedMessage = SUBS + \
                            bencode((
                                    data['channel_id'],
                                    data['infohash'],
                                    binaryBitmask,
                                    [data['subtitles']['eng'], data['subtitles']['ita'],
                                     data['subtitles']['nld']]
                                     ))
        
        list = MockMsgListener()
        self.underTest.registerListener(list) 
        
        #invalid bitmask
        self.underTest._addToRequestedSubtitles(testChannelId, testInfohash, int(0xFFFFFFFF & ~bitmask), None)                   
        
        val = self.underTest.handleMessage(testDestPermId, OLPROTO_VER_FOURTEENTH, expextedMessage)
        # never had a request for this message should be dropped
        self.assertFalse(val)
        self.assertEquals(0,list.subsCount)
        
    def test_receivedSUBSSomeRequest(self):
        langUtil = LanguagesProvider.getLanguagesInstance()
        data = {
                'permid' : testDestPermId,
                'channel_id' : testChannelId,
                'infohash' : testInfohash,
                'subtitles' : {"eng" : "This is content 1", "nld": "This is content  2",
                               "ita" : "This is content 3"},
                'selversion' : OLPROTO_VER_FOURTEENTH
                }
        langs = data['subtitles'].keys()
        
        bitmask = langUtil.langCodesToMask(langs)
        binaryBitmask = pack("!L", bitmask)
        
        expextedMessage = SUBS + \
                            bencode((
                                    data['channel_id'],
                                    data['infohash'],
                                    binaryBitmask,
                                    [data['subtitles']['eng'], data['subtitles']['ita'],
                                     data['subtitles']['nld']]
                                     ))
        
        list = MockMsgListener()
        self.underTest.registerListener(list) 
        
        #invalid bitmask
        self.underTest._addToRequestedSubtitles(testChannelId, testInfohash, langUtil.langCodesToMask(["ita"]), None)                   
        
        val = self.underTest.handleMessage(testDestPermId, OLPROTO_VER_FOURTEENTH, expextedMessage)
        # never had a request for this message should be dropped
        self.assertTrue(val)
        self.assertEquals(1,list.subsCount)
        
        params = list.subsParams[0]
        channel_id, infohash, contentsDictionary = params[1]
        self.assertEquals(testChannelId,channel_id)
        self.assertEquals(testInfohash, infohash)
        contentKeys = contentsDictionary.keys()
        self.assertEquals(["ita"],contentKeys)
        
    def test_cleanSUSRequests(self):
        
        self.underTest._requestValidityTime = 0.001 #ds
        self.underTest._addToRequestedSubtitles(testChannelId, testInfohash, 3, None)
        self.assertEquals(1,len(self.underTest.requestedSubtitles))
        time.sleep(1.2)
        self.underTest._cleanUpRequestedSubtitles()
        self.assertEquals(0,len(self.underTest.requestedSubtitles))
        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestSubtitlesMsgHandlerIsolation)     
        
        
        
        
    
