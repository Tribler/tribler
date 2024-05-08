from __future__ import annotations

from datetime import datetime, timezone

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase

from tribler.core.database.serialization import (
    REGULAR_TORRENT,
    HealthItemsPayload,
    SignedPayload,
    TorrentMetadataPayload,
    UnknownBlobTypeException,
    int2time,
    read_payload_with_offset,
    time2int,
)


class TestSerialization(TestBase):
    """
    Tests for the serialization logic.
    """

    def test_time2int(self) -> None:
        """
        Test if time2int normalizes timestamps based on the supplied epoch.
        """
        date = datetime.fromtimestamp(1234, tz=timezone.utc)
        epoch = datetime.fromtimestamp(1000, tz=timezone.utc)

        self.assertEqual(234, time2int(date, epoch))

    def test_int2time(self) -> None:
        """
        Test if int2time normalizes timestamps based on the supplied epoch.
        """
        epoch = datetime.fromtimestamp(1000, tz=timezone.utc)

        self.assertEqual(datetime.fromtimestamp(1234, tz=timezone.utc), int2time(234, epoch))

    def test_read_payload_with_offset_unknown(self) -> None:
        """
        Test if unknown payload formats throw a UnknownBlobTypeException.
        """
        with self.assertRaises(UnknownBlobTypeException):
            read_payload_with_offset(b"\xFF\xFF")

    def test_read_payload_with_offset_regular_torrent(self) -> None:
        """
        Test if TorrentMetadataPayload payload formats are correctly decoded.
        """
        payload = TorrentMetadataPayload(metadata_type=REGULAR_TORRENT, reserved_flags=0, public_key=b"\x00" * 64,
                                         id_=7, origin_id=1337, timestamp=10, infohash=b"\x01" * 20, size=42,
                                         torrent_date=int2time(0), title="test", tags="tags", tracker_info="")

        unserialized, offset = read_payload_with_offset(payload.serialized())

        self.assertEqual(payload.metadata_type, unserialized.metadata_type)
        self.assertEqual(payload.reserved_flags, unserialized.reserved_flags)
        self.assertEqual(payload.public_key, unserialized.public_key)
        self.assertEqual(payload.id_, unserialized.id_)
        self.assertEqual(payload.origin_id, unserialized.origin_id)
        self.assertEqual(payload.timestamp, unserialized.timestamp)
        self.assertEqual(payload.infohash, unserialized.infohash)
        self.assertEqual(payload.size, unserialized.size)
        self.assertEqual(payload.torrent_date, unserialized.torrent_date)
        self.assertEqual(payload.title, unserialized.title)
        self.assertEqual(payload.tags, unserialized.tags)
        self.assertEqual(payload.tracker_info, unserialized.tracker_info)

    def test_signed_payload_sign(self) -> None:
        """
        Test if signing a SignedPayload and unpacking it, leads to the same payload.
        """
        private_key = default_eccrypto.generate_key("curve25519")
        payload = SignedPayload(9999, 0, private_key.pub().key_to_bin()[10:])

        payload.add_signature(private_key)
        unserialized = SignedPayload.from_signed_blob(payload.serialized() + payload.signature)

        self.assertTrue(payload.has_signature())
        self.assertTrue(payload.check_signature())
        self.assertTrue(unserialized.has_signature())
        self.assertTrue(unserialized.check_signature())
        self.assertEqual(payload.metadata_type, unserialized.metadata_type)
        self.assertEqual(payload.reserved_flags, unserialized.reserved_flags)
        self.assertEqual(payload.public_key, unserialized.public_key)
        self.assertEqual(payload.signature, unserialized.signature)

    def test_signed_payload_to_dict_signed(self) -> None:
        """
        Test if converting a signed SignedPayload to a dict and loading it again, leads to the same payload.
        """
        private_key = default_eccrypto.generate_key("curve25519")
        payload = SignedPayload(9999, 0, private_key.pub().key_to_bin()[10:])
        payload.add_signature(private_key)

        unserialized = SignedPayload.from_dict(**payload.to_dict())

        self.assertTrue(payload.has_signature())
        self.assertTrue(payload.check_signature())
        self.assertTrue(unserialized.has_signature())
        self.assertTrue(unserialized.check_signature())
        self.assertEqual(payload.metadata_type, unserialized.metadata_type)
        self.assertEqual(payload.reserved_flags, unserialized.reserved_flags)
        self.assertEqual(payload.public_key, unserialized.public_key)
        self.assertEqual(payload.signature, unserialized.signature)

    def test_signed_payload_to_dict_unsigned(self) -> None:
        """
        Test if converting an unsigned SignedPayload to a dict and loading it again, leads to the same payload.
        """
        payload = SignedPayload(9999, 0, b"\x00" * 64)

        unserialized = SignedPayload.from_dict(**payload.to_dict())

        self.assertFalse(payload.has_signature())
        self.assertFalse(unserialized.has_signature())
        self.assertEqual(payload.metadata_type, unserialized.metadata_type)
        self.assertEqual(payload.reserved_flags, unserialized.reserved_flags)
        self.assertEqual(payload.public_key, unserialized.public_key)
        self.assertEqual(payload.signature, unserialized.signature)

    def test_get_magnet(self) -> None:
        """
        Test if TorrentMetadataPayload can generated magnet links from its infohash.
        """
        payload = TorrentMetadataPayload(metadata_type=REGULAR_TORRENT, reserved_flags=0, public_key=b"\x00" * 64,
                                         id_=7, origin_id=1337, timestamp=10, infohash=b"\x01" * 20, size=42,
                                         torrent_date=int2time(0), title="test", tags="tags", tracker_info="")

        self.assertEqual("magnet:?xt=urn:btih:0101010101010101010101010101010101010101&dn=test",
                         payload.get_magnet())

    def test_auto_convert_torrent_date(self) -> None:
        """
        Test if TorrentMetadataPayload automatically converts its torrent date from int to datetime.
        """
        payload1 = TorrentMetadataPayload(metadata_type=REGULAR_TORRENT, reserved_flags=0, public_key=b"\x00" * 64,
                                          id_=7, origin_id=1337, timestamp=10, infohash=b"\x01" * 20, size=42,
                                          torrent_date=int2time(0), title="test", tags="tags", tracker_info="")
        payload2 = TorrentMetadataPayload(metadata_type=REGULAR_TORRENT, reserved_flags=0, public_key=b"\x00" * 64,
                                          id_=7, origin_id=1337, timestamp=10, infohash=b"\x01" * 20, size=42,
                                          torrent_date=0, title="test", tags="tags", tracker_info="")

        unserialized1 = TorrentMetadataPayload.from_signed_blob(payload1.serialized() + payload1.signature)
        unserialized2 = TorrentMetadataPayload.from_signed_blob(payload2.serialized() + payload2.signature)

        self.assertEqual(unserialized1.torrent_date, unserialized2.torrent_date)

    def test_health_items_payload(self) -> None:
        """
        Test if HealthItemsPayload is correctly unpacked.
        """
        payload = HealthItemsPayload(b"1,2,3;4,5,6;7,8,9;")

        self.assertEqual([(1, 2, 3), (4, 5, 6), (7, 8, 9)], HealthItemsPayload.unpack(payload.serialize()))

    def test_health_items_payload_no_data(self) -> None:
        """
        Test if HealthItemsPayload without data is correctly unpacked.
        """
        payload = HealthItemsPayload(b"")

        self.assertEqual([], HealthItemsPayload.unpack(payload.serialize()))

    def test_health_items_payload_missing_data(self) -> None:
        """
        Test if HealthItemsPayload with missing data gets error values.
        """
        payload = HealthItemsPayload(b";1,2,3;")

        self.assertEqual([(0, 0, 0), (1, 2, 3)], HealthItemsPayload.unpack(payload.serialize()))

    def test_health_items_payload_illegal_data(self) -> None:
        """
        Test if HealthItemsPayload with illegal data gets error values.
        """
        payload = HealthItemsPayload(b"a,b,c;1,2,3;")

        self.assertEqual([(0, 0, 0), (1, 2, 3)], HealthItemsPayload.unpack(payload.serialize()))

    def test_health_items_payload_negative_data(self) -> None:
        """
        Test if HealthItemsPayload with negatve data gets error values.
        """
        payload = HealthItemsPayload(b"-1,-1,-1;1,2,3;")

        self.assertEqual([(0, 0, 0), (1, 2, 3)], HealthItemsPayload.unpack(payload.serialize()))
