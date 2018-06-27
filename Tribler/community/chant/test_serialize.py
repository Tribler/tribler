import datetime
import unittest

import Tribler.community.chant.testtools as tt
from Tribler.community.chant.MDPackXDR import serialize_metadata_gossip, deserialize_metadata_gossip, MD_DELETE


class TestSerialize(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.crypto = tt.crypto
        self.key = tt.key

        md_del = {"type"       : MD_DELETE,
                  "timestamp"  : datetime.datetime(2005, 7, 14, 12, 30),
                  "tc_pointer" : long(0),
                  "delete_sig" : str(0x1) * 70,
                  "public_key" : tt.public_key}
        self.md_list = [tt.get_regular_md_dict(), md_del]

    def TestSerializeMetadataGossip(self):
        for md_orig in self.md_list:
            md = md_orig
            md_ser = serialize_metadata_gossip(md, self.key)
            md_deser = deserialize_metadata_gossip(md_ser)
            self.assertDictEqual(md, md_deser)

    def TestSerializeSignedMetadataGossip(self):
        for md_orig in self.md_list:
            md = md_orig
            serialize_metadata_gossip(md, self.key)
            md_ser = serialize_metadata_gossip(md)
            md_deser = deserialize_metadata_gossip(md_ser)
            self.assertDictEqual(md, md_deser)
