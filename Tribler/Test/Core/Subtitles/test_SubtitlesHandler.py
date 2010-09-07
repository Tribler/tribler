# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
from Tribler.Core.Overlay.permid import generate_keypair
from Tribler.Test.Core.Subtitles.simple_mocks import  \
    MockOverlayBridge, MockSubsMsgHander, MockMetadataDBHandler, MockSession
from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import LanguagesProvider
import logging
import os
import unittest
import codecs
from Tribler.Core.Subtitles.SubtitlesHandler import SubtitlesHandler,\
    getSubtitleFileRelativeName
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_FOURTEENTH



logging.basicConfig(level=logging.DEBUG)
_keypairs = (generate_keypair(), generate_keypair(), generate_keypair())
testChannelId = str(_keypairs[0].pub().get_der())
testDestPermId = str(_keypairs[1].pub().get_der())
testMyPermId = str(_keypairs[2].pub().get_der())

testInfohash = sha("yoman!").digest()

RES_DIR = os.path.join('..','..','subtitles_test_res')

class TestSubtitlesHandler(unittest.TestCase):


    def setUp(self):
        
        self._session = MockSession()
        self.ol_bridge = MockOverlayBridge()
        self.rmdDBHandler = MockMetadataDBHandler()
        self.underTest = SubtitlesHandler()
    
    def tearDown(self):
        self.ol_bridge = None
        #cleanup the mess in collected dir
        if self.underTest.subs_dir is not None:
            toDelete = [ os.path.join(self.underTest.subs_dir, entry) for entry in os.listdir(self.underTest.subs_dir)\
                        if entry.endswith(".srt")]
        
            for xfile in toDelete:
                if os.path.isfile(xfile) :
                    os.remove(xfile)

    def testRegisterStuff(self):
        self.underTest.register(self.ol_bridge, self.rmdDBHandler, self._session)
        self.assertTrue(self.underTest.registered)
        self.assertTrue(self.ol_bridge is self.underTest.overlay_bridge)
        self.assertTrue(self.rmdDBHandler is self.underTest.subtitlesDb)
        expectedPath = os.path.join(os.path.abspath(os.path.curdir), self._session.get_state_dir(),
                                    "subtitles_collecting_dir")
        self.assertEqual(os.path.normpath(expectedPath), self.underTest.subs_dir)
        # preaparing the mock msg handler
        
        self.mockMsgHandler = MockSubsMsgHander()
        self.underTest._subsMsgHndlr = self.mockMsgHandler
    
    def testGetSubtitlesFileRelativeName(self):
        #subtitles filenames are build from the sha1 hash
        #of the triple (channel_id, infohash, langCode)
        name = getSubtitleFileRelativeName(testChannelId, testInfohash, "rus")
        hasher = sha()
        for value in (testChannelId, testInfohash, "rus"):
            hasher.update(value)
        
        self.assertEquals(hasher.hexdigest() + ".srt", name)
        
    def testSendSubtitleRequestSimple(self):
        self.testRegisterStuff()
        

        self.underTest.sendSubtitleRequest(testDestPermId, testChannelId, testInfohash,
                                           ["zho","rus"], None, OLPROTO_VER_FOURTEENTH)
        
        self.assertEquals(1,self.mockMsgHandler.sendReqCount)

    def testReceibedGETSUBSNoSubs(self):
        self.testRegisterStuff()
        
        self.underTest.receivedSubsRequest(testDestPermId, 
                                           (testDestPermId,testChannelId,["ita","nld"]), OLPROTO_VER_FOURTEENTH)
        
        self.assertEquals(0,self.mockMsgHandler.sendResCount)
        
    def testReceivedGETSUBSTwoSubs(self):
        self.testRegisterStuff()
        self.underTest.receivedSubsRequest(testDestPermId, 
                                           (testChannelId,testInfohash,["eng","rus"]), OLPROTO_VER_FOURTEENTH)
        
        eng = u"this is a fake srt\n\nonly needed for testing\n\ncheers :)\n\n"
        rus = eng + \
                u"asfasgb sagas gba\n\nasfasfas 24214 a \nThe checksum is different yuppy!\n\n"
        
        
        self.assertEquals(1,self.mockMsgHandler.sendResCount)
        destination, response, selversion = self.mockMsgHandler.sendResParams[0]
        self.assertEquals(testDestPermId,destination)
        self.assertEquals(OLPROTO_VER_FOURTEENTH,selversion)
        channelId, infohash, contentsList = response
        self.assertEquals(testChannelId,channelId)
        self.assertEquals(testInfohash,infohash)
        self.assertEquals(contentsList,{"eng":eng,"rus":rus})
        
    
    def testReceivedSUBSMessage(self):
        self.testRegisterStuff()
        languages = ["eng","rus"]
        zho = u"Subtitle Content 1"
        kor = u"Subtitle Content 2"
        contentsDict = {"eng":zho, "rus":kor}
        
        msg = (testChannelId,
               testInfohash, contentsDict)
        
        
        simpleCallback = lambda x : x

        
        bitmask = LanguagesProvider.getLanguagesInstance().langCodesToMask(["eng","rus"])
        self.underTest.receivedSubsResponse(testDestPermId, msg, [(simpleCallback,bitmask)], OLPROTO_VER_FOURTEENTH)
        
        #self.assertEquals(languages,callbackParams)
        expectedFilename1 = getSubtitleFileRelativeName(testChannelId, testInfohash, "eng")
        expectedFilename2 = getSubtitleFileRelativeName(testChannelId, testInfohash, "rus")
        expectedPath1 = os.path.join(self._session.get_state_dir(),self.underTest.subs_dir,expectedFilename1)
        expectedPath2 = os.path.join(self._session.get_state_dir(),self.underTest.subs_dir,expectedFilename2)
        self.assertTrue(os.path.isfile(expectedPath1))
        self.assertTrue(os.path.isfile(expectedPath2))
        
        with codecs.open(expectedPath1,"rb","utf-8") as file1:
            content1 = file1.read()
            
        self.assertEquals(zho,content1)
        
        with codecs.open(expectedPath2,"rb","utf-8") as file2:
            content2 = file2.read()
            
        self.assertEquals(kor,content2)
        
        self.assertEquals(1, self.ol_bridge.add_task_count)
        params = self.ol_bridge.add_taskParametersHistory[0]
        #calling the lambda
        val = params[0]()
        self.assertEquals(languages,val)
        
        
    def test_saveSubsOnDisk(self):
        self.testRegisterStuff()
        subContent = u"Test Content\nFor a pseudo subtitle file\n\nYo!\n"
        self.underTest._saveSubOnDisk(testChannelId, testInfohash,
                                      "eng", subContent)
        expectedFilename = getSubtitleFileRelativeName(testChannelId, 
                                                       testInfohash, "eng")
        expectedPath = os.path.join(self.underTest.subs_dir, expectedFilename)
        self.assertTrue(os.path.isfile(expectedPath))
        
        #check the contents
        with codecs.open(expectedPath, "rb", "utf-8") as file:
            cont = file.read()
        
        self.assertEquals(subContent,cont)
        
        ##now the file exists. If a new subtitle is saved for the same
        # channel, infohash, lang but with a different content
        # the old one should be overwritten
        newContent = u"I'm the new content! I shall win over the old one!"
        self.underTest._saveSubOnDisk(testChannelId, testInfohash,
                                      "eng", newContent)
        self.assertTrue(os.path.isfile(expectedPath))
        #check the contents
        with codecs.open(expectedPath, "rb", "utf-8") as file:
            cont = file.read()
        
        self.assertEquals(newContent,cont)

        
        
        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestSubtitlesHandler)     
        
        
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
    
    

    
