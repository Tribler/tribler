# Written by Andrea Reale
# see LICENSE.txt for license information

from __future__ import with_statement
from Tribler.Core.CacheDB.MetadataDBHandler import MetadataDBHandler
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Test.Core.CacheDB.SimpleMetadataDB import SimpleMetadataDB
from Tribler.Core.Overlay.permid import generate_keypair
import copy
import hashlib
import logging
import random
import unittest
import codecs
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataExceptions import MetadataDBException
import time
import os.path

RES_DIR = os.path.join('..','..','subtitles_test_res')

CREATE_SQL_FILE = os.path.join(RES_DIR,'schema_sdb_v5.sql')
SQL_DB = ":memory:"#"res/test.sdb"

logging.basicConfig(level=logging.DEBUG)


class TestMetadataDBHandler(unittest.TestCase):
    _keypair1 = generate_keypair()
    aPermId = str(_keypair1.pub().get_der())
    _keypair2 = generate_keypair()
    anotherPermId = str(_keypair2.pub().get_der())

    def setUp(self):
        #createDB = not os.path.isfile(SQL_DB)
        self.db = SimpleMetadataDB(CREATE_SQL_FILE, SQL_DB)
        self.underTest = MetadataDBHandler(self.db)
    
    def tearDown(self):
        self.db.close()
        #if os.path.isfile(SQL_DB) :
            #os.remove(SQL_DB)
        
        
    
    def testInitHandler(self):
        self.assertTrue(self.underTest is not None)
        
    def testSingleton(self):
        
        instance1 = MetadataDBHandler.getInstance()
        instance2 = MetadataDBHandler.getInstance()
        self.assertTrue(instance1 is instance2)
        
    def testInsertNewMetadataSubs(self):
        metadataDTO = MockMetadataDTO(["nld","ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
        results = self.db.fetchall(testquery, (bin2str(metadataDTO.channel),bin2str(metadataDTO.infohash)))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(bin2str(metadataDTO.channel),tupl[1])
        self.assertEquals(bin2str(metadataDTO.infohash),tupl[2])
        self.assertEquals(metadataDTO.description, tupl[3])
        self.assertEquals(metadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(metadataDTO.signature), tupl[5])
        
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(2,len(subtitles))
        
        for lang in ("ita", "nld"):
            found = False
            foundSub = None
            for subtuple in subtitles:
                if subtuple[1] == lang:
                    found = True
                    foundSub = subtuple
                    break
                
            self.assertTrue(found)
            self.assertEquals(bin2str(metadataDTO.getSubtitle(lang).checksum), foundSub[3])
            
    
    def testGetMetadataInstance(self):
        metadataDTO = MockMetadataDTO(["nld","ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        retrievedMetadata = self.underTest.getMetadata(metadataDTO.channel,
                                                       metadataDTO.infohash)
        
        self.assertFalse(retrievedMetadata is None)
        self.assertFalse(retrievedMetadata is metadataDTO)
        self.assertEquals(metadataDTO,retrievedMetadata)
        
        
            
    
    def testInsertNewMetadataNoSubs(self):
        metadataDTO = MockMetadataDTO([])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
            
        channel = bin2str(metadataDTO.channel)
        infohash = bin2str(metadataDTO.infohash)
        results = self.db.fetchall(testquery, (channel,infohash))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(channel,tupl[1])
        self.assertEquals(infohash,tupl[2])
        self.assertEquals(metadataDTO.description, tupl[3])
        self.assertEquals(metadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(metadataDTO.signature), tupl[5])
        
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(0,len(subtitles))
    
    def testUpdateExistingWithOlder(self):
        
        
        metadataDTO = MockMetadataDTO(["nld", "ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        olderMetadataDTO = copy.copy(metadataDTO)
        olderMetadataDTO.timestamp = 1 #*really* old
        olderMetadataDTO.sign(olderMetadataDTO._keypair)
    
        self.underTest.insertMetadata(olderMetadataDTO)
        
        #assert the the older did not replace the newer
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
        channel = bin2str(metadataDTO.channel)
        infohash = bin2str(metadataDTO.infohash)
        results = self.db.fetchall(testquery, (channel,infohash))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(channel,tupl[1])
        self.assertEquals(infohash,tupl[2])
        self.assertEquals(metadataDTO.description, tupl[3])
        self.assertEquals(metadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(metadataDTO.signature), tupl[5])
        
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(2,len(subtitles))
        
        for lang in ("ita", "nld"):
            found = False
            foundSub = None
            for subtuple in subtitles:
                if subtuple[1] == lang:
                    found = True
                    foundSub = subtuple
                    break
                
            self.assertTrue(found)
            self.assertEquals(bin2str(metadataDTO.getSubtitle(lang).checksum), foundSub[3])
        
        
    def testUpdateExistingWithNewerSameSub(self):
        metadataDTO = MockMetadataDTO(["nld", "ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        newerMetadataDTO = copy.copy(metadataDTO)
        newerMetadataDTO.description = u"I'm newer!"
        newerMetadataDTO.timestamp = newerMetadataDTO.timestamp +1 #newer 
        newerMetadataDTO.sign(newerMetadataDTO._keypair)
        
        
        self.underTest.insertMetadata(newerMetadataDTO)
        
        #assert the the older has been replaced
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
        
        channel = bin2str(metadataDTO.channel)
        infohash = bin2str(metadataDTO.infohash)
        results = self.db.fetchall(testquery, (channel,infohash))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(channel,tupl[1])
        self.assertEquals(infohash,tupl[2])
        self.assertEquals(newerMetadataDTO.description, tupl[3])
        self.assertEquals(newerMetadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(newerMetadataDTO.signature), tupl[5])
        
        #testing subtitles with the old once since they are not changed
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(2,len(subtitles))
        
        for lang in ("ita", "nld"):
            found = False
            foundSub = None
            for subtuple in subtitles:
                if subtuple[1] == lang:
                    found = True
                    foundSub = subtuple
                    break
                
            self.assertTrue(found)
            self.assertEquals(bin2str(metadataDTO.getSubtitle(lang).checksum), foundSub[3])
    
    
    
    def testUpdateExistingWithNewerNewSubs(self):
        metadataDTO = MockMetadataDTO(["nld", "ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        newerMetadataDTO = MockMetadataDTO(["nld","ita","eng"])
        newerMetadataDTO.channel = metadataDTO.channel
        newerMetadataDTO.infohash = metadataDTO.infohash
        newerMetadataDTO._keypair = metadataDTO._keypair
        newerMetadataDTO.timestamp = metadataDTO.timestamp +1 #newer 
        newerMetadataDTO.sign(newerMetadataDTO._keypair)
        
        
        self.underTest.insertMetadata(newerMetadataDTO)
        
        #assert the the older has been replaced
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
            
        channel = bin2str(metadataDTO.channel)
        infohash = bin2str(metadataDTO.infohash)
        results = self.db.fetchall(testquery, (channel,infohash))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(channel,tupl[1])
        self.assertEquals(infohash,tupl[2])
        self.assertEquals(newerMetadataDTO.description, tupl[3])
        self.assertEquals(newerMetadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(newerMetadataDTO.signature), tupl[5])
        
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(3,len(subtitles))
        
        for lang in ("ita", "nld","eng"):
            found = False
            foundSub = None
            for subtuple in subtitles:
                if subtuple[1] == lang:
                    found = True
                    foundSub = subtuple
                    break
                
            self.assertTrue(found)
            self.assertEquals(bin2str(newerMetadataDTO.getSubtitle(lang).checksum), foundSub[3])
    
    def testUpdateExistingWithNewerSubsDeleted(self):
        metadataDTO = MockMetadataDTO(["nld", "ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        newerMetadataDTO = MockMetadataDTO(["nld","eng"])
        newerMetadataDTO.channel = metadataDTO.channel
        newerMetadataDTO.infohash = metadataDTO.infohash
        newerMetadataDTO._keypair = metadataDTO._keypair
        newerMetadataDTO.timestamp = metadataDTO.timestamp +1 #newer 
        newerMetadataDTO.sign(newerMetadataDTO._keypair)
        
        
        self.underTest.insertMetadata(newerMetadataDTO)
        
        #assert the the older has been replaced
        testquery = "SELECT * FROM Metadata WHERE publisher_id=?" \
            + " AND infohash=?;" 
        channel = bin2str(metadataDTO.channel)
        infohash = bin2str(metadataDTO.infohash)
        results = self.db.fetchall(testquery, (channel,infohash))
        
        self.assertTrue(len(results) == 1)
        tupl = results[0] 
        self.assertTrue(tupl[0] is not None and isinstance(tupl[0], int))
        self.assertEquals(channel,tupl[1])
        self.assertEquals(infohash,tupl[2])
        self.assertEquals(newerMetadataDTO.description, tupl[3])
        self.assertEquals(newerMetadataDTO.timestamp, tupl[4])
        self.assertEquals(bin2str(newerMetadataDTO.signature), tupl[5])
        
        subtitlesQuery = "SELECT * FROM Subtitles WHERE metadata_id_fk=?;"
        
        subtitles = self.db.fetchall(subtitlesQuery, (tupl[0],))
        self.assertEquals(2,len(subtitles))
        
        for lang in ("nld","eng"):
            found = False
            foundSub = None
            for subtuple in subtitles:
                if subtuple[1] == lang:
                    found = True
                    foundSub = subtuple
                    break
                
            self.assertTrue(found)
            self.assertEquals(bin2str(newerMetadataDTO.getSubtitle(lang).checksum), foundSub[3])
    
    def testGetAllMetadataForInfohashEmtpy(self):
        metadataDTO = MockMetadataDTO(["nld", "ita"])
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        
        otherinfohash = _generateFakeInfohash()
        
        results = self.underTest.getAllMetadataForInfohash(otherinfohash)
        self.assertTrue(len(results)==0)
    
    def testGetAllMetadataForInfohashNotEmpty(self):
        infohash = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld", "ita"],infohash)
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        #different channels since the channel is automatically
        #generated by MockMetadata DTO
        metadataDTO2 = MockMetadataDTO(["rus", "eng"],infohash)
        metadataDTO2.sign(metadataDTO2._keypair)
        self.underTest.insertMetadata(metadataDTO2)
        
        #a 3rd instance with different channel and infohash
        metadataDTO3 = MockMetadataDTO(["rus", "spa", "jpn"])
        metadataDTO3.sign(metadataDTO3._keypair)
        self.underTest.insertMetadata(metadataDTO3)
        
        results = self.underTest.getAllMetadataForInfohash(infohash)
        self.assertTrue(len(results)==2)
        
        #in checks for equality, not reference equality
        self.assertTrue(metadataDTO1 in results)
        self.assertTrue(metadataDTO2 in results)
        self.assertFalse(metadataDTO3 in results)
        
        
        
    def testDeleteSubtitle(self):
        infohash = _generateFakeInfohash()
        metadataDTO = MockMetadataDTO(["eng","kor"], infohash)
        
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        res = self.underTest.getAllSubtitles(metadataDTO.channel, infohash)
        self.assertTrue("eng" in res and "kor" in res)
        
        #delete a subtitle that does not exist
        self.underTest._deleteSubtitleByChannel(metadataDTO.channel, infohash, "ita")
        res = self.underTest.getAllSubtitles(metadataDTO.channel, infohash)
        self.assertTrue("eng" in res and "kor" in res)
        
        self.underTest._deleteSubtitleByChannel(metadataDTO.channel, infohash, "eng")
        res = self.underTest.getAllSubtitles(metadataDTO.channel, infohash)
        self.assertTrue("kor" in res and not "eng" in res)
        
        
    def testSelectLocalSubtitles(self):
        
        infohash1 = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["eng","kor"], infohash1)
           
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        res = self.underTest.getAllLocalSubtitles()
        
        self.assertTrue(len(res) == 0)
        
        infohash2 = _generateFakeInfohash()
        metadataDTO2 = MockMetadataDTO(["nld","spa"], infohash2)
        
        metadataDTO2.getSubtitle("nld").path = "/bla/bla"
        
        metadataDTO2.sign(metadataDTO2._keypair)
        self.underTest.insertMetadata(metadataDTO2)
        
        res = self.underTest.getAllLocalSubtitles()
        
        self.assertTrue(len(res) == 1)
        
        self.assertTrue(metadataDTO2.channel in res)
        
        self.assertTrue(infohash2 in res[metadataDTO2.channel])
        self.assertEquals(1, len(res[metadataDTO2.channel][infohash2]))
        
        self.assertEquals(metadataDTO2.getSubtitle("nld"), res[metadataDTO2.channel][infohash2][0])
        
    def testSelectLocalSubtitles2(self):
        infohash1 = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["eng","kor", "nld"], infohash1)
        
        metadataDTO1.getSubtitle("nld").path = "/bla/bla"
        metadataDTO1.getSubtitle("eng").path = "/bla/bla"
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        infohash2 = _generateFakeInfohash()
        metadataDTO2 = MockMetadataDTO(["ita","spa"], infohash2)
        metadataDTO2.getSubtitle("ita").path = "/a/b"
        metadataDTO2.getSubtitle("spa").path = "/c/d"
        metadataDTO2.sign(metadataDTO2._keypair)
        self.underTest.insertMetadata(metadataDTO2)
        
        
        res = self.underTest.getLocalSubtitles(metadataDTO1.channel, infohash1)
        self.assertEquals(2, len(res))

        self.assertTrue("eng" in res)
        self.assertEquals(metadataDTO1.getSubtitle("eng"), res["eng"])
        
        self.assertTrue("nld" in res)
        self.assertEquals(metadataDTO1.getSubtitle("nld"), res["nld"])
        
        self.assertFalse("kor" in res)
        
    def testUpdateSubtitlesWithNonePathValue(self):
        
        
        infohash1 = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["eng","kor"], infohash1)
        
        metadataDTO1.getSubtitle("eng").path = os.path.abspath(os.path.join("bla","bla"))
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        sub = self.underTest.getSubtitle(metadataDTO1.channel, infohash1, "eng")
        self.assertEquals(os.path.abspath(os.path.join("bla","bla")), sub.path)
        
        self.underTest.updateSubtitlePath(metadataDTO1.channel, infohash1,
                                          "eng", None, True)
        
        sub = self.underTest.getSubtitle(metadataDTO1.channel, infohash1, "eng")
        self.assertEquals(None, sub.path)
        
        
    def testUpdateSubtitles(self):
        sub1path= os.path.join(RES_DIR,"fake0.srt")
        sub2path=os.path.join(RES_DIR,"fake1.srt")
        infohash = _generateFakeInfohash()
        metadataDTO = MockMetadataDTO([], infohash)
        sub1 = SubtitleInfo("ita", None, _computeSHA1(sub1path))
        sub2 = SubtitleInfo("eng",None,_computeSHA1(sub2path))
        
        metadataDTO.addSubtitle(sub1)
        metadataDTO.addSubtitle(sub2)
        metadataDTO.sign(metadataDTO._keypair)
        self.underTest.insertMetadata(metadataDTO)
        
        res1 = self.underTest.getSubtitle(metadataDTO.channel, infohash,"ita")
        self.assertEquals(sub1,res1)
        
        res2 = self.underTest.getSubtitle(metadataDTO.channel, infohash, "eng")
        self.assertEquals(sub2,res2)
        
        sub1bis = copy.copy(sub1)
        sub1bis.path = sub1path
        sub2bis = copy.copy(sub2)
        sub2bis.path = sub2path
        
        self.underTest.updateSubtitlePath(metadataDTO.channel, infohash, 
                                      sub1bis.lang, sub1bis.path, False)
        self.underTest.updateSubtitlePath(metadataDTO.channel, infohash, 
                                      sub2bis.lang, sub2bis.path , False)
        
        
        self.underTest.commit()
        
        #still unchanged since I did not commit
        res1 = self.underTest.getSubtitle(metadataDTO.channel, infohash,"ita")
        self.assertTrue(sub1== res1 and sub1.path != res1.path)
        self.assertTrue(sub1bis == res1 and sub1bis.path == res1.path)
        
        res2 = self.underTest.getSubtitle(metadataDTO.channel, infohash, "eng")
        self.assertTrue(sub2 == res2 and sub2.path != res2.path)
        self.assertTrue(sub2bis == res2 and sub2bis.path == res2.path)
        
        
    # 30-05-2010 Testing of the new added table (SubtitlesHave) manipulation
    # methods.
    
    def testInsertAndGetHaveMask(self):
       
        
        infohash = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld","spa"], infohash)
        channel = metadataDTO1.channel
        
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        peer_id = TestMetadataDBHandler.anotherPermId
        
        #inserting a negative mask has to be refused
        havemask = -1
        funcToTest =\
            lambda : self.underTest.insertHaveMask(channel, infohash, 
                                                   peer_id, havemask)
        
        self.assertRaises(MetadataDBException, funcToTest)
        
        #also a bitmask must be smaller then 2**32
        havemask = 2**32
        
        funcToTest =\
            lambda : self.underTest.insertHaveMask(channel, infohash, 
                                                   peer_id, havemask)
        
        self.assertRaises(MetadataDBException, funcToTest)
        
        
        #now it's time for a correct value
        havemask1=0x80000001
        self.underTest.insertHaveMask(channel, infohash, peer_id, havemask1)
        
        mask = self.underTest.getHaveMask(channel, infohash,peer_id)
        self.assertEqual(mask,havemask1)
        
        #duplicate insertions should raise an error
        havemask2=0xffffffff
        funcToTest = \
           lambda : self.underTest.insertHaveMask(channel, infohash, 
                                                  peer_id, havemask2)
        
        self.assertRaises(MetadataDBException, funcToTest)
        
        #insertion for another peer should go fine
        self.underTest.insertHaveMask(channel, infohash, channel, havemask2)
        
        mask1 = self.underTest.getHaveMask(channel, infohash,peer_id)
        self.assertEqual(mask1,havemask1)
        mask2 = self.underTest.getHaveMask(channel, infohash,channel)
        self.assertEqual(mask2,havemask2)
        
        #getting an have mask for an unexistent channel, infohash shall
        #return None
        mask1 = \
            self.underTest.getHaveMask(channel, _generateFakeInfohash(),peer_id)
        self.assertTrue(mask1 is None)
        
        #as it should happen for asking for an unexisting peer_id
        mask1 = self.underTest.getHaveMask(channel, infohash,
                                           TestMetadataDBHandler.aPermId)
        self.assertTrue(mask1 is None)
        
    def testUpdateHaveMask(self):
        infohash = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld","spa"], infohash)
        channel = metadataDTO1.channel
        
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        peer_id = TestMetadataDBHandler.anotherPermId
        
        
        #adding an have mask to the db
        havemask1=0x80000001
        self.underTest.insertHaveMask(channel, infohash, peer_id, havemask1)
        
        mask = self.underTest.getHaveMask(channel, infohash,peer_id)
        self.assertEqual(mask,havemask1)
        
        #updating it to a different value
        new_havemask = 0x1111ffff
        self.underTest.updateHaveMask(channel, infohash, peer_id, 
                                      new_havemask)
        mask = self.underTest.getHaveMask(channel, infohash,peer_id)
        self.assertEqual(mask,new_havemask)
        
        #trying to update a non existing row should cause an error
        # -- currently this doesn't happen
        # implementing this beahaviour would slow down the db
        #funcToTest = \
        #    lambda: self.underTest.updateHaveMask(channel, infohash, 
        #                                         channel, new_havemask)
        # self.assertRaises(MetadataDBException, funcToTest)
    
    
    def testDeleteHaveEntry(self):
        infohash = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld","spa"], infohash)
        channel = metadataDTO1.channel
        
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        peer_id = TestMetadataDBHandler.anotherPermId
        
        
        #adding an have mask to the db
        havemask1=0x80000001
        self.underTest.insertHaveMask(channel, infohash, peer_id, havemask1)
        
        havemask2=0x02324123
        self.underTest.insertHaveMask(channel, infohash, channel, havemask2)
        
        self.underTest.deleteHaveEntry(channel, infohash, peer_id)
        
        mask = self.underTest.getHaveMask(channel, infohash, peer_id)
        self.assertTrue(mask is None)
        
        mask = self.underTest.getHaveMask(channel, infohash, channel)
        self.assertEquals(havemask2,mask)
        
        # deleting an entry that does not exist should leave
        # the db unchanged
        self.underTest.deleteHaveEntry(channel, infohash, peer_id)
        
        mask = self.underTest.getHaveMask(channel, infohash, channel)
        self.assertEquals(havemask2,mask)
        
    
    def testGetAllHaveEntries(self):
        
        infohash = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld","spa"], infohash)
        channel = metadataDTO1.channel
        
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        peer_id = TestMetadataDBHandler.anotherPermId
        
        
        #adding an have mask to the db
        havemask1=0x80000001
        self.underTest.insertHaveMask(channel, infohash, peer_id, havemask1)
        
        time.sleep(1) # otherwise they would have the same timestamp
        havemask2=0x02324123
        self.underTest.insertHaveMask(channel, infohash, channel, havemask2)
        
        d = self.underTest.getHaveEntries(channel, infohash)
        
        #the second inserted havemask has to be returned first
        # since it is newer
        firstTuple = d[0]
        self.assertEquals(channel, firstTuple[0])
        self.assertEquals(havemask2,firstTuple[1])
        self.assertTrue(firstTuple[2] is not None)
        
        self.assertEquals(peer_id, d[1][0])
        self.assertEquals(havemask1,d[1][1])
        self.assertTrue(d[1][2] is not None)
        
        
    
    def testCleanUpAllHave(self):
        infohash1 = _generateFakeInfohash()
        metadataDTO1 = MockMetadataDTO(["nld","spa"], infohash1)
        channel1 = metadataDTO1.channel
        
        metadataDTO1.sign(metadataDTO1._keypair)
        self.underTest.insertMetadata(metadataDTO1)
        
        infohash2 = _generateFakeInfohash()
        metadataDTO2 = MockMetadataDTO(["nld","spa"], infohash2)
        channel2 = metadataDTO2.channel
        
        metadataDTO2.sign(metadataDTO2._keypair)
        self.underTest.insertMetadata(metadataDTO2)
        
        
        peer_id1 = TestMetadataDBHandler.anotherPermId
        peer_id2 = TestMetadataDBHandler.aPermId
        
        #inserting some data: 4 have maskes for each of the two channels with
        # custom timestamps
        # older then 1275295300
        self.underTest.insertHaveMask(channel1, infohash1, channel1, 0x42, 1275295290)
        self.underTest.insertHaveMask(channel1, infohash1, peer_id1, 0x42, 1275295291)
        # newer then 1275295300
        self.underTest.insertHaveMask(channel1, infohash1, peer_id2, 0x42, 1275295300)
        self.underTest.insertHaveMask(channel1, infohash1, channel2, 0x42, 1275295301)
        
        
        # older then 1275295300
        self.underTest.insertHaveMask(channel2, infohash2, channel1, 0x42, 1275295290)
        self.underTest.insertHaveMask(channel2, infohash2, peer_id1, 0x42, 1275295291)
        
        # newer then 1275295300
        self.underTest.insertHaveMask(channel2, infohash2, peer_id2, 0x42, 1275295300)
        self.underTest.insertHaveMask(channel2, infohash2, channel2, 0x42, 1275295301)
        
        self.underTest.cleanupOldHave(1275295300)
        haveForEntry1 = self.underTest.getHaveEntries(channel1, infohash1)
        expectedList1 = [(channel2,0x42,1275295301), (peer_id2, 0x42, 1275295300), 
                         (channel1, 0x42, 1275295290)]
        self.assertEquals(expectedList1, haveForEntry1)
        
        haveForEntry2 = self.underTest.getHaveEntries(channel2, infohash2)
        expectedList2 = [(channel2, 0x42, 1275295301),(peer_id2, 0x42, 1275295300)]
        self.assertEquals(expectedList2,haveForEntry2)
        
        
        
        
    
    
def _generateFakeInfohash():
    hasher = hashlib.sha1()
    hasher.update(str(random.randint(0,65535)))
    return hasher.digest()

def _computeSHA1(path):
    hasher = hashlib.sha1()
    with codecs.open(path, "rb", "utf-8") as file:
        contents = file.read()
    
    hasher.update(contents)
    return hasher.digest()
        
        


class MockMetadataDTO(MetadataDTO):
  
    
    def __init__(self, availableLangs, infohash = None):
        
        self._keypair = generate_keypair()
        
        self._permId = str(self._keypair.pub().get_der())
        
        if infohash == None :
            hasher = hashlib.sha1()
            hasher.update(self._permId + "a")
            infohash = hasher.digest()
        
        self.channel = self._permId
        self.infohash = infohash
        self.description = u""
        self.resetTimestamp()
        self._subtitles = {}
        
        hasher = hashlib.sha1() #fake checksums for subs
        
        for lang in availableLangs:
            hasher.update(lang + "123")
            checksum = hasher.digest()
            self.addSubtitle(SubtitleInfo(lang, None, checksum))
            
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestMetadataDBHandler)
            
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testInitHandler']
    unittest.main()