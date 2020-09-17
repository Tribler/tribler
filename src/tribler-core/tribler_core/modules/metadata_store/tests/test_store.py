import os
import random
import string
from binascii import unhexlify
from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.keyvault.private.libnaclkey import LibNaCLSK

from pony.orm import db_session, flush

from tribler_core.modules.metadata_store.discrete_clock import clock
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH, entries_to_chunk
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.serialization import (
    CHANNEL_TORRENT,
    ChannelMetadataPayload,
    DeletedMetadataPayload,
    SignedPayload,
    UnknownBlobTypeException,
)
from tribler_core.modules.metadata_store.store import (
    DELETED_METADATA,
    GOT_NEWER_VERSION,
    MetadataStore,
    NO_ACTION,
    UNKNOWN_CHANNEL,
    UNKNOWN_TORRENT,
    UPDATED_OUR_VERSION,
)
from tribler_core.tests.tools.base_test import TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.random_utils import random_infohash

TEST_PERSONAL_KEY = LibNaCLSK(
    b'4c69624e61434c534b3af56022aa5d556c07aeed704ee98df7dca580f'
    b'522e1405663f0d36508d2189cb8991af2dd27b34bc18b4d24869e2c4f2cfdb164a78ea6e687daf7a21640d62b1b'[10:]
)


def get_payloads(entity_class):
    c = entity_class(infohash=database_blob(random_infohash()))
    payload = c._payload_class.from_signed_blob(c.serialized())
    deleted_payload = DeletedMetadataPayload.from_signed_blob(c.serialized_delete())
    return c, payload, deleted_payload


def make_wrong_payload(filename):
    key = default_eccrypto.generate_key(u"curve25519")
    metadata_payload = SignedPayload(
        666, 0, database_blob(key.pub().key_to_bin()[10:]), signature=b'\x00' * 64, skip_key_check=True
    )
    with open(filename, 'wb') as output_file:
        output_file.write(metadata_payload.serialized())


SAMPLE_DIR = TESTS_DATA_DIR / 'sample_channel'
# Just get the first and only subdir there, and assume it is the sample channel dir
CHANNEL_DIR = [
    SAMPLE_DIR / subdir
    for subdir in os.listdir(SAMPLE_DIR)
    if (SAMPLE_DIR / subdir).is_dir() and len(subdir) == CHANNEL_DIR_NAME_LENGTH
][0]
CHANNEL_METADATA = TESTS_DATA_DIR / 'sample_channel' / 'channel.mdblob'


class TestMetadataStore(TriblerCoreTest):
    """
    This class contains tests for the metadata store.
    """

    async def setUp(self):
        await super(TestMetadataStore, self).setUp()
        self.mds = MetadataStore(":memory:", self.session_base_dir, TEST_PERSONAL_KEY)
        clock.clock = 1000

    async def tearDown(self):
        self.mds.shutdown()
        await super(TestMetadataStore, self).tearDown()

    @db_session
    def test_process_channel_dir_file(self):
        """
        Test whether we are able to process files in a directory containing node metadata
        """

        test_node_metadata = self.mds.TorrentMetadata(title='test', infohash=database_blob(random_infohash()))
        metadata_path = self.session_base_dir / 'metadata.data'
        test_node_metadata.to_file(metadata_path)
        # We delete this TorrentMeta info now, it should be added again to the database when loading it
        test_node_metadata.delete()
        loaded_metadata = self.mds.process_mdblob_file(metadata_path, skip_personal_metadata_payload=False)
        self.assertEqual(loaded_metadata[0][0].title, 'test')

        # Test whether we delete existing metadata when loading a DeletedMetadata blob
        metadata = self.mds.TorrentMetadata(infohash=b'1' * 20)
        metadata.to_delete_file(metadata_path)
        loaded_metadata = self.mds.process_mdblob_file(metadata_path, skip_personal_metadata_payload=False)
        # Make sure the original metadata is deleted
        self.assertEqual(loaded_metadata[0], (None, 6))
        self.assertIsNone(self.mds.TorrentMetadata.get(infohash=b'1' * 20))

        # Test an unknown metadata type, this should raise an exception
        invalid_metadata = self.session_base_dir / 'invalidtype.mdblob'
        make_wrong_payload(invalid_metadata)
        self.assertRaises(
            UnknownBlobTypeException,
            self.mds.process_mdblob_file,
            invalid_metadata,
            skip_personal_metadata_payload=False,
        )

    @db_session
    def test_squash_mdblobs(self):
        chunk_size = self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT
        md_list = [
            self.mds.TorrentMetadata(
                title=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
                infohash=database_blob(random_infohash()),
                torrent_date=datetime.utcfromtimestamp(100),
            )
            for _ in range(0, 10)
        ]
        chunk, _ = entries_to_chunk(md_list, chunk_size=chunk_size)
        dict_list = [d.to_dict()["signature"] for d in md_list]
        for d in md_list:
            d.delete()
        self.assertListEqual(
            dict_list,
            [
                d[0].to_dict()["signature"]
                for d in self.mds.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
            ],
        )

    def test_squash_mdblobs_multiple_chunks(self):
        with db_session:
            md_list = [
                self.mds.TorrentMetadata(
                    title=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
                    infohash=database_blob(random_infohash()),
                    torrent_date=datetime.utcfromtimestamp(100),
                )
                for _ in range(0, 10)
            ]
            # Test splitting into multiple chunks
            chunk, index = entries_to_chunk(md_list, chunk_size=900)
            chunk2, _ = entries_to_chunk(md_list, chunk_size=900, start_index=index)
            dict_list = [d.to_dict()["signature"] for d in md_list]

            for d in md_list:
                d.delete()
        self.assertListEqual(
            dict_list[:index],
            [
                d[0].to_dict()["signature"]
                for d in self.mds.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
            ],
        )

        self.assertListEqual(
            dict_list[index:],
            [
                d[0].to_dict()["signature"]
                for d in self.mds.process_compressed_mdblob(chunk2, skip_personal_metadata_payload=False)
            ],
        )

    @db_session
    def test_multiple_squashed_commit_and_read(self):
        """
        Test committing entries into several squashed blobs and reading them back
        """
        self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT = 500

        num_entries = 10
        channel = self.mds.ChannelMetadata.create_channel('testchan')
        md_list = [
            self.mds.TorrentMetadata(
                origin_id=channel.id_, title='test' + str(x), status=NEW, infohash=database_blob(random_infohash())
            )
            for x in range(0, num_entries)
        ]
        channel.commit_channel_torrent()

        channel.local_version = 0
        for md in md_list:
            md.delete()

        channel_dir = self.mds.ChannelMetadata._channels_dir / channel.dirname
        self.assertTrue(len(os.listdir(channel_dir)) > 1)  # make sure it was broken into more than one .mdblob file
        self.mds.process_channel_dir(channel_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False)
        self.assertEqual(num_entries, len(channel.contents))

    @db_session
    def test_skip_processing_of_received_personal_channel_torrents(self):
        """
        Test that personal torrent is ignored by default when processing the torrent metadata payload
        """
        channel = self.mds.ChannelMetadata.create_channel('testchan')
        torrent_md = self.mds.TorrentMetadata(
            origin_id=channel.id_, title='test', status=NEW, infohash=database_blob(random_infohash())
        )
        channel.commit_channel_torrent()
        torrent_md.delete()

        channel_dir = self.mds.ChannelMetadata._channels_dir / channel.dirname
        self.assertTrue(len(os.listdir(str_path(channel_dir))) > 0)

        # By default, personal channel torrent metadata processing is skipped so there should be no torrents
        # added to the channel
        channel.local_version = 0
        self.mds.process_channel_dir(channel_dir, channel.public_key, channel.id_)
        self.assertEqual(0, len(channel.contents))

        # Enable processing of personal channel torrent metadata
        channel.local_version = 0
        self.mds.process_channel_dir(channel_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False)
        self.assertEqual(1, len(channel.contents))

    @db_session
    def test_skip_processing_mdblob_with_forbidden_terms(self):
        """
        Test that an mdblob with forbidden terms cannot ever get into the local database
        """
        key = default_eccrypto.generate_key(u"curve25519")
        chan_entry = self.mds.ChannelMetadata(title=u"12yo", infohash=database_blob(random_infohash()), sign_with=key)
        chan_payload = chan_entry._payload_class(**chan_entry.to_dict())
        chan_entry.delete()
        self.assertEqual(self.mds.process_payload(chan_payload), [(None, NO_ACTION)])

    @db_session
    def test_process_invalid_compressed_mdblob(self):
        """
        Test whether processing an invalid compressed mdblob does not crash Tribler
        """
        self.assertFalse(self.mds.process_compressed_mdblob(b"abcdefg"))

    @db_session
    def test_process_channel_dir(self):
        """
        Test processing a directory containing metadata blobs
        """
        payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA)
        channel = self.mds.process_payload(payload)[0][0]
        self.assertFalse(channel.contents_list)
        self.mds.process_channel_dir(CHANNEL_DIR, channel.public_key, channel.id_)
        self.assertEqual(len(channel.contents_list), 4)
        self.assertEqual(channel.timestamp, 1565621688015)
        self.assertEqual(channel.local_version, channel.timestamp)

    @db_session
    def test_process_payload(self):

        _, node_payload, node_deleted_payload = get_payloads(self.mds.ChannelNode)

        self.mds.ChannelNode._my_key = default_eccrypto.generate_key(u"curve25519")
        self.assertFalse(self.mds.process_payload(node_payload))
        self.assertEqual([(None, DELETED_METADATA)], self.mds.process_payload(node_deleted_payload))
        # Do nothing in case it is unknown/abstract payload type, like ChannelNode
        self.assertFalse(self.mds.process_payload(node_payload))

        # Check if node metadata object is properly created on payload processing
        node, node_payload, node_deleted_payload = get_payloads(self.mds.TorrentMetadata)
        node_dict = node.to_dict()
        node.delete()
        result = self.mds.process_payload(node_payload)
        self.assertEqual(UNKNOWN_TORRENT, result[0][1])
        self.assertEqual(node_dict['metadata_type'], result[0][0].to_dict()['metadata_type'])

        # Check the same for a channel
        node, node_payload, node_deleted_payload = get_payloads(self.mds.ChannelMetadata)
        node_dict = node.to_dict()
        node.delete()

        # Check that there is no action if the signature on the delete object is unknown
        self.assertFalse(self.mds.process_payload(node_deleted_payload))
        result = self.mds.process_payload(node_payload)
        self.assertEqual(UNKNOWN_CHANNEL, result[0][1])
        self.assertEqual(node_dict['metadata_type'], result[0][0].to_dict()['metadata_type'])

    @db_session
    def test_process_payload_update_type(self):
        # Check if applying class-changing update to an entry works
        # First, create a node and get a payload from it, then update it to another type, then get payload
        # for the updated version, then delete the updated version, then bring back the original one by processing it,
        # then try processing the payload of updated version and see if it works. Phew!
        node, node_payload, node_deleted_payload = get_payloads(self.mds.CollectionNode)
        updated_node = node.update_properties(
            {"origin_id": 0}
        )  # This will implicitly change the node to ChannelTorrent
        self.assertEqual(updated_node.metadata_type, CHANNEL_TORRENT)
        updated_node_payload = updated_node._payload_class.from_signed_blob(updated_node.serialized())
        updated_node.delete()

        old_node, _ = self.mds.process_payload(node_payload, skip_personal_metadata_payload=False)[0]
        updated_node2, _ = self.mds.process_payload(updated_node_payload, skip_personal_metadata_payload=False)[0]
        self.assertEqual(updated_node2.metadata_type, CHANNEL_TORRENT)

    @db_session
    def test_process_payload_ffa(self):
        infohash = b"1" * 20
        ffa_torrent = self.mds.TorrentMetadata.add_ffa_from_dict(dict(infohash=infohash, title='abc'))
        ffa_payload = self.mds.TorrentMetadata._payload_class.from_signed_blob(ffa_torrent.serialized())
        ffa_torrent.delete()

        # Assert that FFA is never added to DB if there is already a signed entry with the same infohash
        signed_md = self.mds.TorrentMetadata(infohash=infohash, title="sdfsdfsdf")
        signed_md_payload = self.mds.TorrentMetadata._payload_class.from_signed_blob(signed_md.serialized())
        self.assertEqual([(None, NO_ACTION)], self.mds.process_payload(ffa_payload))
        signed_md.delete()

        # Add an FFA from the payload
        md, result = self.mds.process_payload(ffa_payload)[0]
        self.assertEqual(UNKNOWN_TORRENT, result)
        self.assertTrue(md)

        # Assert that older FFAs are never replaced by newer ones with the same infohash
        self.assertEqual([(None, NO_ACTION)], self.mds.process_payload(ffa_payload))

        # Assert that FFA entry is replaced by a signed entry when we receive one with the same infohash
        self.mds.process_payload(signed_md_payload, skip_personal_metadata_payload=False)
        self.assertEqual(
            database_blob(signed_md_payload.signature), self.mds.TorrentMetadata.get(infohash=infohash).signature
        )

    @db_session
    def test_process_payload_merge_entries(self):
        # Check the corner case where the new entry must replace two old entries: one with a matching infohash, and
        # another one with a non-matching id
        node = self.mds.TorrentMetadata(infohash=database_blob(random_infohash()))
        node_dict = node.to_dict()
        node.delete()

        node2 = self.mds.TorrentMetadata(infohash=database_blob(random_infohash()))
        node2_dict = node2.to_dict()
        node2.delete()

        node_updated = self.mds.TorrentMetadata(
            infohash=node_dict["infohash"], id_=node2_dict["id_"], timestamp=node2_dict["timestamp"] + 1
        )
        node_updated_payload = node_updated._payload_class.from_signed_blob(node_updated.serialized())
        node_updated.delete()

        self.mds.TorrentMetadata(**node_dict)
        self.mds.TorrentMetadata(**node2_dict)

        result = self.mds.process_payload(node_updated_payload, skip_personal_metadata_payload=False)
        self.assertIn((None, DELETED_METADATA), result)
        self.assertIn((self.mds.TorrentMetadata.get(), UPDATED_OUR_VERSION), result)
        self.assertEqual(
            database_blob(self.mds.TorrentMetadata.select()[:][0].signature),
            database_blob(node_updated_payload.signature),
        )

    @db_session
    def test_process_payload_reject_older(self):
        # Check there is no action if the processed payload has a timestamp that is less than the
        # local_version of the corresponding local channel. (I.e. remote peer trying to push back a deleted entry)
        channel = self.mds.ChannelMetadata(
            title='bla', version=123, timestamp=10, local_version=12, infohash=database_blob(random_infohash())
        )
        torrent = self.mds.TorrentMetadata(
            title='blabla', timestamp=11, origin_id=channel.id_, infohash=database_blob(random_infohash())
        )
        payload = torrent._payload_class(**torrent.to_dict())
        torrent.delete()
        self.assertEqual([(None, NO_ACTION)], self.mds.process_payload(payload, skip_personal_metadata_payload=False))

    @db_session
    def test_process_payload_reject_older_entry_with_known_infohash_or_merge(self):
        # Check there is no action if the processed payload has a timestamp that is less than the
        # local_version of the corresponding local channel. (I.e. remote peer trying to push back a deleted entry)
        torrent = self.mds.TorrentMetadata(
            title='blabla', timestamp=10, id_=10, infohash=database_blob(random_infohash())
        )
        payload = torrent._payload_class(**torrent.to_dict())
        torrent.delete()

        torrent2 = self.mds.TorrentMetadata(title='blabla', timestamp=11, id_=3, infohash=payload.infohash)
        payload2 = torrent._payload_class(**torrent2.to_dict())
        torrent2.delete()

        torrent3 = self.mds.TorrentMetadata(title='blabla', timestamp=12, id_=4, infohash=payload.infohash)
        payload3 = torrent._payload_class(**torrent3.to_dict())
        torrent3.delete()

        # Test rejecting older entry with the same infohash
        self.mds.process_payload(payload2, skip_personal_metadata_payload=False)
        self.assertEqual(
            GOT_NEWER_VERSION, self.mds.process_payload(payload, skip_personal_metadata_payload=False)[0][1]
        )

        # In this corner case the newly arrived payload contains a newer node
        # that has the same infohash as the one that is already there.
        # The older one should be deleted, and the newer one should be installed instead.
        results = self.mds.process_payload(payload3, skip_personal_metadata_payload=False)
        self.assertIn((None, DELETED_METADATA), results)
        self.assertIn((self.mds.TorrentMetadata.get(), UNKNOWN_TORRENT), results)

    @db_session
    def test_process_payload_reject_older_entry(self):
        torrent_old = self.mds.TorrentMetadata(
            title='blabla', timestamp=11, id_=3, infohash=database_blob(random_infohash())
        )
        payload_old = torrent_old._payload_class(**torrent_old.to_dict())
        torrent_old.delete()

        torrent_updated = self.mds.TorrentMetadata(
            title='blabla', timestamp=12, id_=3, infohash=database_blob(random_infohash())
        )
        torrent_updated_dict = torrent_updated.to_dict()
        torrent_updated.delete()
        flush()

        self.mds.TorrentMetadata.from_dict(torrent_updated_dict)

        # Test rejecting older version of the same entry with a different infohash
        self.assertEqual(
            GOT_NEWER_VERSION, self.mds.process_payload(payload_old, skip_personal_metadata_payload=False)[0][1]
        )

    @db_session
    def test_get_num_channels_nodes(self):
        self.mds.ChannelMetadata(title='testchan', id_=0, infohash=database_blob(random_infohash()))
        self.mds.ChannelMetadata(title='testchan', id_=123, infohash=database_blob(random_infohash()))
        self.mds.ChannelMetadata(
            title='testchan',
            id_=0,
            public_key=unhexlify('0' * 20),
            signature=unhexlify('0' * 64),
            skip_key_check=True,
            infohash=database_blob(random_infohash()),
        )
        self.mds.ChannelMetadata(
            title='testchan',
            id_=0,
            public_key=unhexlify('1' * 20),
            signature=unhexlify('1' * 64),
            skip_key_check=True,
            infohash=database_blob(random_infohash()),
        )

        _ = [
            self.mds.TorrentMetadata(title='test' + str(x), status=NEW, infohash=database_blob(random_infohash()))
            for x in range(0, 3)
        ]

        self.assertEqual(4, self.mds.get_num_channels())
        self.assertEqual(3, self.mds.get_num_torrents())
