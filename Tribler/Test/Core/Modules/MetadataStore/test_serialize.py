# -*- coding: utf-8 -*-
import datetime
import unittest
from copy import deepcopy

import Tribler.Test.Core.Modules.MetadataStore.tools as tt
from Tribler.Core.Modules.MetadataStore.serialization import float2time, time2float, serialize_metadata_gossip, \
    deserialize_metadata_gossip, MetadataTypes, EPOCH


class TestSerialize(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.crypto = tt.crypto
        self.key = tt.key

        self.md_dict = {}

        self.md_dict["typeless"] = {
            "type": MetadataTypes.TYPELESS.value,
            "timestamp": datetime.datetime(2005, 7, 14, 12, 30),
            "tc_pointer": long(0),
            "public_key": tt.public_key}

        self.md_dict["regular_torrent"] = deepcopy(self.md_dict["typeless"])
        self.md_dict["regular_torrent"].update(
            {
                "type": MetadataTypes.REGULAR_TORRENT.value,
                "infohash": str(0x1) * 20,
                "torrent_date": datetime.datetime(2002, 7, 14, 12, 10),
                "size": long(123),
                "title": u'bla bla йух',
                "tags": "la la"})

        self.md_dict["channel_torrent"] = deepcopy(
            self.md_dict["regular_torrent"])
        self.md_dict["channel_torrent"].update(
            {"type": MetadataTypes.CHANNEL_TORRENT.value, "version": 333})

        self.md_dict["deleted"] = deepcopy(self.md_dict["typeless"])
        self.md_dict["deleted"].update({"type": MetadataTypes.DELETED.value,
                                        "delete_signature": str(0x1) * 70})

    def tst_serialize_unsigned(self, dct):
        # Test serializing and signing
        md_ser = serialize_metadata_gossip(dct, self.key)
        md_deser = deserialize_metadata_gossip(md_ser)
        self.assertDictEqual(dct, md_deser)

    def tst_serialize_signed(self, dct):
        # Test repacking already signed
        md_ser = serialize_metadata_gossip(dct)
        md_deser = deserialize_metadata_gossip(md_ser)
        self.assertDictEqual(dct, md_deser)

    def tst_serialize(self, dct):
        # Achtung! These subtests are order dependent! 1st one adds signature to dict!
        self.tst_serialize_unsigned(dct)
        self.tst_serialize_signed(dct)

    def test_serialize_typeless(self):
        self.tst_serialize(self.md_dict["typeless"])

    def test_serialize_regular_torrent(self):
        self.tst_serialize(self.md_dict["regular_torrent"])

    def test_serialize_channel_torrent(self):
        self.tst_serialize(self.md_dict["channel_torrent"])

    def test_serialize_deleted(self):
        self.tst_serialize(self.md_dict["deleted"])


class TestTimeutils(unittest.TestCase):

    def setUp(self):
        self.test_time_list = [
            datetime.datetime(2005, 7, 14, 12, 30, 12, 1234),
            datetime.datetime(2039, 7, 14, 12, 30, 12, 1234),
            datetime.datetime.utcnow()]

    def test_time_convert(self):
        for tm in self.test_time_list:
            self.assertTrue(tm == float2time(time2float(tm)))

    def test_zero_time(self):
        self.assertTrue(float2time(0.0) == EPOCH)

    def test_negative_time(self):
        negtm = EPOCH - datetime.timedelta(1)
        self.assertTrue(negtm == float2time(time2float(negtm)))
