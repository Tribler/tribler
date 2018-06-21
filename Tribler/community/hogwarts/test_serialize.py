import unittest
#import ch
import MDPackXDR
import datetime
from timeutils import time2float, float2time
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto



class TestSerialize(unittest.TestCase):

    def setUp(self):
        self.md_entry_empty = MDPackXDR.MetadataTMP()
        self.md_entry1 = MDPackXDR.MetadataTMP()
        self.md_entry1.type = 1
        self.md_entry1.infohash = str(0x1)*20
        self.md_entry1.date = datetime.datetime(2005, 7, 14, 12, 30)
        self.md_entry1.tags = "tag1.tag2. tag3 . tag4:bla."

        self.crypto = ECCrypto()
        self.key = self.crypto.generate_key('curve25519')

        self.gsp_entry = MDPackXDR.GossipTMP()
        self.gsp_entry.type = 1
        self.gsp_entry.tc_pointer = 123
        self.gsp_entry.content = "1234567"
        self.gsp_entry.date = datetime.datetime(2005, 7, 14, 12, 30)
        self.gsp_entry.public_key = self.key.pub().key_to_bin()
        pass

    def TestSerializeMetadata(self):
        md = self.md_entry1
        md_ser = MDPackXDR.serialize_metadata(md)
        md_deser = MDPackXDR.deserialize_metadata(md_ser)
        self.assertDictEqual(md.__dict__, md_deser.__dict__)

    def TestSerializeEmpty(self):
        md = self.md_entry_empty
        md_ser = MDPackXDR.serialize_metadata(md)
        md_deser = MDPackXDR.deserialize_metadata(md_ser)
        self.assertDictEqual(md.__dict__, md_deser.__dict__)

    def TestSerializeGossip(self):
        gsp = self.gsp_entry
        gsp_ser = MDPackXDR.serialize_gossip(self.key, gsp)
        gsp_deser = MDPackXDR.deserialize_gossip(gsp_ser)
        # The original gsp does not have sig, so we have to copy it
        # for check to be correct
        gsp.sig = gsp_deser.sig
        self.assertDictEqual(gsp.__dict__, gsp_deser.__dict__)





