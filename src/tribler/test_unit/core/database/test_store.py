from __future__ import annotations

from ipv8.community import Community, CommunitySettings
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8
from pony.orm import db_session

from tribler.core.database.orm_bindings.torrent_metadata import entries_to_chunk
from tribler.core.database.serialization import NULL_KEY, int2time
from tribler.core.database.store import MetadataStore, ObjState


class MockCommunity(Community):
    """
    An empty community.
    """

    community_id = b"\x00" * 20


class TestMetadataStore(TestBase[MockCommunity]):
    """
    Tests for the MetadataStore class.
    """

    def setUp(self) -> None:
        """
        Create a single node and its metadata store.
        """
        super().setUp()
        self.initialize(MockCommunity, 1)
        self.metadata_store = MetadataStore(":memory:", self.private_key(0), check_tables=False)

    def create_node(self, settings: CommunitySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False) -> MockIPv8:
        """
        Create a node with a curve25519 key.
        """
        return MockIPv8("curve25519", MockCommunity, settings, create_dht, enable_statistics)

    @db_session
    def test_squash_mdblobs(self) -> None:
        """
        Test if mdblobs can be squashed and processed again.
        """
        md_list = [
            self.metadata_store.TorrentMetadata(title=f'test torrent {i}', infohash=bytes([i]) * 20,
                                                torrent_date=int2time(i))
            for i in range(10)
        ]
        chunk, _ = entries_to_chunk(md_list, chunk_size=999999999999999)
        signatures = [d.signature for d in md_list]
        for d in md_list:
            d.delete()

        uncompressed = self.metadata_store.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)

        self.assertEqual(signatures, [d.md_obj.signature for d in uncompressed])

    @db_session
    def test_squash_mdblobs_multiple_chunks(self) -> None:
        """
        Test if multiple mdblobs can be squashed and processed again.
        """
        md_list = [
            self.metadata_store.TorrentMetadata(title=f'test torrent {i}', infohash=bytes([i]) * 20, id_=i,
                                                torrent_date=int2time(i), timestamp=i)
            for i in range(10)
        ]
        for md in md_list:
            md.public_key = self.metadata_store.my_public_key_bin
            md.signature = md.serialized(self.metadata_store.my_key)[-64:]
        # Test splitting into multiple chunks
        chunks1, index = entries_to_chunk(md_list, chunk_size=1)
        chunks2, _ = entries_to_chunk(md_list, chunk_size=999999999999999, start_index=index)
        signatures = [d.signature for d in md_list]
        for d in md_list:
            d.delete()

        uncompressed1 = self.metadata_store.process_compressed_mdblob(chunks1, skip_personal_metadata_payload=False)
        uncompressed2 = self.metadata_store.process_compressed_mdblob(chunks2, skip_personal_metadata_payload=False)

        self.assertEqual(signatures[:index], [d.md_obj.signature for d in uncompressed1])
        self.assertEqual(signatures[index:], [d.md_obj.signature for d in uncompressed2])

    @db_session
    def test_process_invalid_compressed_mdblob(self) -> None:
        """
        Test if an invalid compressed mdblob does not crash Tribler.
        """
        self.assertEqual([], self.metadata_store.process_compressed_mdblob(b"abcdefg"))

    @db_session
    def test_process_forbidden_null_key_payload(self) -> None:
        """
        Test if payloads with NULL keys are not processed.
        """
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0,
                                                 torrent_date=int2time(0), timestamp=0, public_key=NULL_KEY)
        payload = md.payload_class.from_dict(**md.to_dict())

        self.assertEqual([], self.metadata_store.process_payload(payload))

    @db_session
    def test_process_forbidden_type_payload(self) -> None:
        """
        Test if payloads that are not torrent type are not processed.
        """
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0,
                                                 torrent_date=int2time(0), timestamp=0, public_key=NULL_KEY)
        payload = md.payload_class.from_dict(**md.to_dict())
        payload.metadata_type = 9999

        self.assertEqual([], self.metadata_store.process_payload(payload))

    @db_session
    def test_process_external_payload(self) -> None:
        """
        Test if processing an external payload works.
        """
        other_key = default_eccrypto.generate_key("curve25519")
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0, timestamp=0,
                                                 torrent_date=int2time(0), public_key=other_key.key_to_bin())
        payload = md.payload_class.from_signed_blob(md.serialized(other_key))

        # Check if node metadata object is properly created on payload processing
        result, = self.metadata_store.process_payload(payload)
        self.assertEqual(ObjState.NEW_OBJECT, result.obj_state)
        self.assertEqual(payload.metadata_type, result.md_obj.to_dict()['metadata_type'])

        # Check that we flag this as duplicate in case we already know about the local node
        result, = self.metadata_store.process_payload(payload)
        self.assertEqual(ObjState.DUPLICATE_OBJECT, result.obj_state)

    @db_session
    def test_process_external_payload_invalid_sig(self) -> None:
        """
        Test that payloads with an invalid signature are not processed.
        """
        other_key = default_eccrypto.generate_key("curve25519")
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0, timestamp=0,
                                                 torrent_date=int2time(0), public_key=other_key.key_to_bin())
        payload = md.payload_class.from_signed_blob(md.serialized(other_key))
        payload.signature = bytes(127 ^ byte for byte in payload.signature)
        md.delete()

        self.assertEqual([], self.metadata_store.process_payload(payload))

    @db_session
    def test_process_payload_invalid_metadata_type(self) -> None:
        """
        Test if payloads with an invalid metadata type are not processed.
        """
        other_key = default_eccrypto.generate_key("curve25519")
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0, timestamp=0,
                                                 torrent_date=int2time(0), public_key=other_key.key_to_bin())
        payload = md.payload_class.from_signed_blob(md.serialized(other_key))
        payload.metadata_type = -1
        md.delete()

        self.assertEqual([], self.metadata_store.process_payload(payload))

    @db_session
    def test_process_payload_skip_personal(self) -> None:
        """
        Test if payloads with our own signature are not processed.
        """
        md = self.metadata_store.TorrentMetadata(title="test torrent", infohash=b"\x01" * 20, id_=0, timestamp=0,
                                                 torrent_date=int2time(0), public_key=self.key_bin(0))
        payload = md.payload_class.from_signed_blob(md.serialized(self.private_key(0)))
        md.delete()

        self.assertEqual([], self.metadata_store.process_payload(payload))

    @db_session
    def test_process_payload_ffa(self) -> None:
        """
        Test if FFA entries are correctly added.
        """
        infohash = b"1" * 20
        ffa_title = "abcabc"
        ffa_torrent = self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": infohash, "title": ffa_title})
        ffa_payload = self.metadata_store.TorrentMetadata.payload_class.from_signed_blob(ffa_torrent.serialized())
        ffa_torrent.delete()

        # Assert that FFA is never added to DB if there is already a signed entry with the same infohash
        signed_md = self.metadata_store.TorrentMetadata(infohash=infohash, title='')
        self.metadata_store.TorrentMetadata.payload_class.from_signed_blob(signed_md.serialized())
        self.assertEqual([], self.metadata_store.process_payload(ffa_payload))
        self.assertIsNone(self.metadata_store.TorrentMetadata.get(title=ffa_title))
        signed_md.delete()

        # Add an FFA from the payload
        result = self.metadata_store.process_payload(ffa_payload)[0]
        self.assertEqual(ObjState.NEW_OBJECT, result.obj_state)
        self.assertIsNotNone(self.metadata_store.TorrentMetadata.get(title=ffa_title))
        self.assertEqual([], self.metadata_store.process_payload(ffa_payload))

    @db_session
    def test_ffa_with_tracker_info(self) -> None:
        """
        Test if FFA entries are correctly added when they have tracker_info.
        """
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"1" * 20,
                                                               "title": "abcabc",
                                                               "tracker_info": b"http://tracker/announce"})

    @db_session
    def test_get_entries_query_sort_by_size(self) -> None:
        """
        Test if entries are properly sorted by size.
        """
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xab" * 20, "title": "abc", "size": 20})
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xcd" * 20, "title": "def", "size": 1})
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xef" * 20, "title": "ghi", "size": 10})

        ordered1, ordered2, ordered3 = self.metadata_store.get_entries_query(sort_by="size", sort_desc=True)[:]
        self.assertEqual(20, ordered1.size)
        self.assertEqual(10, ordered2.size)
        self.assertEqual(1, ordered3.size)

    @db_session
    def test_get_entries_query_deprecated(self) -> None:
        """
        Test if the get entries query ignores invalid arguments.
        """
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xab" * 20, "title": "abc", "size": 20})
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xcd" * 20, "title": "def", "size": 1})
        self.metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xef" * 20, "title": "ghi", "size": 10})

        ordered1, ordered2, ordered3 = self.metadata_store.get_entries_query(sort_by="size", sort_desc=True,
                                                                             exclude_deleted="1")[:]
        self.assertEqual(20, ordered1.size)
        self.assertEqual(10, ordered2.size)
        self.assertEqual(1, ordered3.size)
