import unittest
#import ch
import MDPackXDR
import datetime
from timeutils import time2float, float2time
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
import copy



class TestSerialize(unittest.TestCase):

    def setUp(self):

        self.maxDiff = None
        self.crypto = ECCrypto()
        self.key = self.crypto.generate_key('curve25519')

        date = datetime.datetime(2005, 7, 14, 12, 30)
        self.md = {
            "type" : MDPackXDR.CHANNEL_TORRENT,
            "infohash" : str(0x1)*20,
            "title" : "bla",
            "tags" : "tag1.tag2. tag3 . tag4:bla.",
            "size" : 3,
            "timestamp" : datetime.datetime(2005, 7, 14, 12, 30),
            "torrent_date" : datetime.datetime(2005, 7, 14, 12, 30),
            "tc_pointer" : 0,
            "public_key" : self.key.pub().key_to_bin()}

    def TestSerializeMetadataGossip(self):
        md = copy.deepcopy(self.md)
        md_ser = MDPackXDR.serialize_metadata_gossip(md, self.key)
        md_deser = MDPackXDR.deserialize_metadata_gossip(md_ser)
        self.assertDictEqual(md, md_deser)

    def TestSerializeSignedMetadataGossip(self):
        md = copy.deepcopy(self.md)
        MDPackXDR.serialize_metadata_gossip(md, self.key)
        md_ser = MDPackXDR.serialize_metadata_gossip(md)
        md_deser = MDPackXDR.deserialize_metadata_gossip(md_ser)
        self.assertDictEqual(md, md_deser)





