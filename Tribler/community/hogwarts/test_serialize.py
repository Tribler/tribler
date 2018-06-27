import unittest
#import ch
from MDPackXDR import serialize_metadata_gossip, deserialize_metadata_gossip, MD_DELETE, CHANNEL_TORRENT
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
        md = {
            "type" : CHANNEL_TORRENT,
            "infohash" : str(0x1)*20,
            "title" : "bla",
            "tags" : "tag1.tag2. tag3 . tag4:bla.",
            "size" : 3,
            "timestamp" : datetime.datetime(2005, 7, 14, 12, 30),
            "torrent_date" : datetime.datetime(2005, 7, 14, 12, 30),
            "tc_pointer" : 0,
            "public_key" : self.key.pub().key_to_bin()}

        md_del = {
            "type" : MD_DELETE,
            "timestamp" : datetime.datetime(2005, 7, 14, 12, 30),
            "tc_pointer" : 0,
            "delete_sig" : "bla-bla",
            "public_key" : self.key.pub().key_to_bin()}
        self.md_list = [md, md_del]

    def TestSerializeMetadataGossip(self):
        for md_orig in self.md_list:
            md = copy.deepcopy(md_orig)
            md_ser = serialize_metadata_gossip(md, self.key)
            md_deser = deserialize_metadata_gossip(md_ser)
            self.assertDictEqual(md, md_deser)

    def TestSerializeSignedMetadataGossip(self):
        for md_orig in self.md_list:
            md = copy.deepcopy(md_orig)
            serialize_metadata_gossip(md, self.key)
            md_ser = serialize_metadata_gossip(md)
            md_deser = deserialize_metadata_gossip(md_ser)
            self.assertDictEqual(md, md_deser)





