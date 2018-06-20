import unittest
#import ch
import MDPackXDR
import datetime
from timeutils import time2float, float2time



class TestSerialize(unittest.TestCase):

    def setUp(self):
        self.md_entry_empty = MDPackXDR.MetadataTMP()
        self.md_entry1 = MDPackXDR.MetadataTMP()
        self.md_entry1.type = 1
        self.md_entry1.infohash = str(0x1)*20
        self.md_entry1.date = datetime.datetime(2005, 7, 14, 12, 30)
        self.md_entry1.tags = "tag1.tag2. tag3 . tag4:bla."
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
        



