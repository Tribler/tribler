# Written by Andrea Reale
# see LICENSE.txt for license information

import unittest
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
import Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO as MDUtil
from Tribler.Core.Overlay.permid import generate_keypair
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
import time
from Tribler.Core.BitTornado.bencode import bdecode
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.Subtitles.MetadataDomainObjects.Languages import LanguagesProvider
from Tribler.Core.Utilities.utilities import str2bin
import os.path
from struct import pack

RES_DIR = os.path.join('..','..','..','subtitles_test_res')

test_keypair = generate_keypair()
test_perm_id = str(test_keypair.pub().get_der())


class TestMetadataDTO(unittest.TestCase):

    def setUp(self):
        self._srtSubs = {"eng": os.path.join(RES_DIR, "fake.srt"),"ita": os.path.join(RES_DIR,"fake1.srt"), "rus" : os.path.join(RES_DIR, "fake2.srt")}
    def testMetadataDTOInit(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        self.assertFalse(dto is None)
        self.assertEqual(test_perm_id,dto.channel)
        self.assertEquals(badInfohash,dto.infohash)
        current = time.time()
        self.assertTrue(current -1 <= int(dto.timestamp) <= current)
        self.assertEquals("",dto.description)
        self.assertEquals({}, dto._subtitles)
        self.assertTrue(dto.signature is None)
        
    def test_packData(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        dto.description = u"Sample Description\u041f"
        
        bla = dto._packData()
        decoded = bdecode(bla)
        
        self.assertTrue(len(decoded) == 6)
        decodedChannelId = decoded[0]
        decodedInfohash = decoded[1]
        decodedDescription = decoded[2].decode("utf-8")
        decodedTimestamp = decoded[3]
        bin_decodedBitmask = decoded[4]
        decodedBitmask, = unpack("!L", bin_decodedBitmask)
        self.assertEquals(dto.channel, decodedChannelId)
        self.assertEquals(dto.infohash, decodedInfohash)
        self.assertEquals(dto.description,decodedDescription)
        self.assertAlmostEquals(dto.timestamp,decodedTimestamp)
        self.assertEquals(0,decodedBitmask)
        self.assertEquals(0,len(decoded[5]))
        
    def test_packDataWithSubs(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        
        subtitles = [SubtitleInfo(lang,path) for lang,path in self._srtSubs.iteritems()]
        
        for sub in subtitles :
            sub.computeChecksum()
            dto.addSubtitle(sub)
        
        packed = dto._packData()
        decoded = bdecode(packed)
        
        self.assertTrue(len(decoded) == 6)
        decodedChannelId = decoded[0]
        decodedInfohash = decoded[1]
        decodedDescription = decoded[2]
        decodedTimestamp = decoded[3]
        decodedBitmask = decoded[4]
        checksums = decoded[5]
        
        expectedMask = \
          LanguagesProvider.getLanguagesInstance().langCodesToMask(self._srtSubs.keys())
          
        binaryExpexted = pack("!L", expectedMask)
        
        self.assertEquals(dto.channel, decodedChannelId)
        self.assertEquals(dto.infohash, decodedInfohash)
        self.assertEquals(dto.description,decodedDescription)
        self.assertAlmostEquals(dto.timestamp,decodedTimestamp)
        self.assertEquals(binaryExpexted,decodedBitmask)
        self.assertEquals(3,len(checksums))
        
        subs = dto.getAllSubtitles()
        i=0
        for key in sorted(subs.iterkeys()):
            self.assertEquals(subs[key].checksum, checksums[i])
            i += 1
            

    
    def testSignature(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        
        dto.sign(test_keypair)
        self.assertTrue(dto.verifySignature())
        dto.timestamp = 2
        ok = dto.verifySignature()
        self.assertFalse(ok)
    
    def testSignatureOnChecksums(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        
        subtitles = [SubtitleInfo(lang,path) for lang,path in self._srtSubs.iteritems()]
        
        for sub in subtitles :
            sub.computeChecksum()
            dto.addSubtitle(sub)
        
        
        dto.sign(test_keypair)
        self.assertTrue(dto.verifySignature())
        
        dto.getSubtitle("rus").checksum = "ABCDEFGHILMOPQRS"
        
        self.assertFalse(dto.verifySignature())
    
    def testSerialize(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        dto.description = u"Sample Description"
        dto.sign(test_keypair)
        
        serialized = dto.serialize()
        self.assertEquals(7, len(serialized))
        signature = serialized[6]
        self.assertEquals(dto.signature,signature)
        #the rest is tested with test_packData
    
    def testSerializeWithSubs(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        
        subtitles = [SubtitleInfo(lang,path) for lang,path in self._srtSubs.iteritems()]
        
        for sub in subtitles :
            sub.computeChecksum()
            dto.addSubtitle(sub)
        dto.sign(test_keypair)
        
        serial = dto.serialize()
        decoded = serial
        self.assertEquals(7, len(decoded))
        signature = decoded[6]
        self.assertEquals(dto.signature,signature)
        #the rest is tested with test_packDataWithSubs
        
        
    def testDesrialize(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        dto.description = u"Sample Description"
        dto.sign(test_keypair)
        
        serialized = dto.serialize()
        newDto = MDUtil.deserialize(serialized)
        self.assertEquals(dto,newDto)
        
    def testDeserializeWithSubs(self):
        badInfohash = str2bin("GEh/o8rtTLB1wZJzFcSZSS4u9qo=")
        dto = MetadataDTO(test_perm_id, badInfohash)
        
        subtitles = [SubtitleInfo(lang,path) for lang,path in self._srtSubs.iteritems()]
        
        for sub in subtitles :
            sub.computeChecksum()
            dto.addSubtitle(sub)
        dto.sign(test_keypair)
        
        serial = dto.serialize()
        newDto = MDUtil.deserialize(serial)
        self.assertEquals(dto,newDto)
        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestMetadataDTO)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testMetadataDTOInit']
    unittest.main()
