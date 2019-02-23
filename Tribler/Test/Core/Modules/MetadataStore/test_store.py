from __future__ import absolute_import

import os
import random
import string
from binascii import unhexlify

from pony.orm import db_session

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH, entries_to_chunk
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload, DeletedMetadataPayload, \
    SignedPayload, UnknownBlobTypeException
from Tribler.Core.Modules.MetadataStore.store import DELETED_METADATA, GOT_SAME_VERSION, MetadataStore, NO_ACTION, \
    UNKNOWN_CHANNEL, UNKNOWN_TORRENT
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


def make_wrong_payload(filename):
    key = default_eccrypto.generate_key(u"curve25519")
    metadata_payload = SignedPayload(666, 0, database_blob(key.pub().key_to_bin()[10:]),
                                     signature='\x00'*64, skip_key_check=True)
    with open(filename, 'wb') as output_file:
        output_file.write(''.join(metadata_payload.serialized()))


class TestMetadataStore(TriblerCoreTest):
    """
    This class contains tests for the metadata store.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    SAMPLE_DIR = os.path.join(DATA_DIR, 'sample_channel')
    # Just get the first and only subdir there, and assume it is the sample channel dir
    CHANNEL_DIR = [os.path.join(SAMPLE_DIR, subdir) for subdir in os.listdir(SAMPLE_DIR) if
                   os.path.isdir(os.path.join(SAMPLE_DIR, subdir)) and len(subdir) == CHANNEL_DIR_NAME_LENGTH][0]
    CHANNEL_METADATA = os.path.join(DATA_DIR, 'sample_channel', 'channel.mdblob')

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadataStore, self).setUp()
        my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(":memory:", self.session_base_dir, my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestMetadataStore, self).tearDown()

    def test_store_clock(self):
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds2 = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir, my_key)
        tick = mds2.clock.tick()
        mds2.shutdown()
        mds2 = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir, my_key)
        self.assertEqual(mds2.clock.clock, tick)
        mds2.shutdown()

    @db_session
    def test_process_channel_dir_file(self):
        """
        Test whether we are able to process files in a directory containing node metadata
        """

        test_node_metadata = self.mds.TorrentMetadata(title='test')
        metadata_path = os.path.join(self.session_base_dir, 'metadata.data')
        test_node_metadata.to_file(metadata_path)
        # We delete this TorrentMeta info now, it should be added again to the database when loading it
        test_node_metadata.delete()
        loaded_metadata = self.mds.process_mdblob_file(metadata_path)
        self.assertEqual(loaded_metadata[0][0].title, 'test')

        # Test whether we delete existing metadata when loading a DeletedMetadata blob
        metadata = self.mds.TorrentMetadata(infohash='1' * 20)
        metadata.to_delete_file(metadata_path)
        loaded_metadata = self.mds.process_mdblob_file(metadata_path)
        # Make sure the original metadata is deleted
        self.assertEqual(loaded_metadata[0], (None, 7))
        self.assertIsNone(self.mds.TorrentMetadata.get(infohash='1' * 20))

        # Test an unknown metadata type, this should raise an exception
        invalid_metadata = os.path.join(self.session_base_dir, 'invalidtype.mdblob')
        make_wrong_payload(invalid_metadata)
        self.assertRaises(UnknownBlobTypeException, self.mds.process_mdblob_file, invalid_metadata)

    @db_session
    def test_squash_mdblobs(self):
        chunk_size = self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT
        md_list = [self.mds.TorrentMetadata(
            title=''.join(random.choice(string.ascii_uppercase + string.digits)
                          for _ in range(20))) for _ in range(0, 10)]
        chunk, _ = entries_to_chunk(md_list, chunk_size=chunk_size)
        dict_list = [d.to_dict()["signature"] for d in md_list]
        for d in md_list:
            d.delete()
        self.assertListEqual(dict_list, [d[0].to_dict()["signature"]
                                         for d in self.mds.process_compressed_mdblob(chunk)])

    @db_session
    def test_squash_mdblobs_multiple_chunks(self):
        md_list = [self.mds.TorrentMetadata(title=''.join(random.choice(string.ascii_uppercase + string.digits)
                                                          for _ in range(20))) for _ in range(0, 10)]
        # Test splitting into multiple chunks
        chunk, index = entries_to_chunk(md_list, chunk_size=900)
        chunk2, _ = entries_to_chunk(md_list, chunk_size=900, start_index=index)
        dict_list = [d.to_dict()["signature"] for d in md_list]
        for d in md_list:
            d.delete()
        self.assertListEqual(dict_list[:index], [d[0].to_dict()["signature"]
                                                 for d in self.mds.process_compressed_mdblob(chunk)])
        self.assertListEqual(dict_list[index:], [d[0].to_dict()["signature"]
                                                 for d in self.mds.process_compressed_mdblob(chunk2)])

    @db_session
    def test_multiple_squashed_commit_and_read(self):
        """
        Test committing entries into several squashed blobs and reading them back
        """
        self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT = 500

        num_entries = 10
        channel = self.mds.ChannelMetadata(title='testchan')
        md_list = [self.mds.TorrentMetadata(title='test' + str(x), status=NEW) for x in range(0, num_entries)]
        channel.commit_channel_torrent()

        channel.local_version = 0
        for md in md_list:
            md.delete()

        channel_dir = os.path.join(self.mds.channels_dir, channel.dir_name)
        self.assertTrue(len(os.listdir(channel_dir)) > 1)  # make sure it was broken into more than one .mdblob file
        self.mds.process_channel_dir(channel_dir, channel.public_key)
        self.assertEqual(num_entries, len(channel.contents))

    @db_session
    def test_process_channel_dir(self):
        """
        Test processing a directory containing metadata blobs
        """
        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)
        channel = self.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertFalse(channel.contents_list)
        self.mds.process_channel_dir(self.CHANNEL_DIR, channel.public_key)
        self.assertEqual(len(channel.contents_list), 3)
        self.assertEqual(channel.timestamp, 1551110113007)
        self.assertEqual(channel.local_version, channel.timestamp)

    @db_session
    def test_process_payload(self):
        def get_payloads(entity_class):
            c = entity_class()
            payload = c._payload_class.from_signed_blob(c.serialized())
            deleted_payload = DeletedMetadataPayload.from_signed_blob(c.serialized_delete())
            return c, payload, deleted_payload

        _, node_payload, node_deleted_payload = get_payloads(self.mds.ChannelNode)

        self.assertEqual((None, GOT_SAME_VERSION), self.mds.process_payload(node_payload))
        self.assertEqual((None, DELETED_METADATA), self.mds.process_payload(node_deleted_payload))
        # Do nothing in case it is unknown/abstract payload type, like ChannelNode
        self.assertEqual((None, NO_ACTION), self.mds.process_payload(node_payload))

        # Check if node metadata object is properly created on payload processing
        node, node_payload, node_deleted_payload = get_payloads(self.mds.TorrentMetadata)
        node_dict = node.to_dict()
        node.delete()
        result = self.mds.process_payload(node_payload)
        self.assertEqual(UNKNOWN_TORRENT, result[1])
        self.assertEqual(node_dict['metadata_type'], result[0].to_dict()['metadata_type'])

        # Check the same for a channel
        node, node_payload, node_deleted_payload = get_payloads(self.mds.ChannelMetadata)
        node_dict = node.to_dict()
        node.delete()
        # Check there is no action if the signature on the delete object is unknown
        self.assertEqual((None, NO_ACTION), self.mds.process_payload(node_deleted_payload))
        result = self.mds.process_payload(node_payload)
        self.assertEqual(UNKNOWN_CHANNEL, result[1])
        self.assertEqual(node_dict['metadata_type'], result[0].to_dict()['metadata_type'])

    @db_session
    def test_process_payload_reject_old(self):
        # Check there is no action if the processed payload has a timestamp that is less than the
        # local_version of the corresponding local channel. (I.e. remote peer trying to push back a deleted entry)
        channel = self.mds.ChannelMetadata(title='bla', version=123, local_version=12)
        torrent = self.mds.TorrentMetadata(title='blabla', timestamp=11, origin_id=channel.id_)
        payload = torrent._payload_class(**torrent.to_dict())
        torrent.delete()
        self.assertEqual((None, NO_ACTION), self.mds.process_payload(payload))

    @db_session
    def test_get_num_channels_nodes(self):
        self.mds.ChannelMetadata(title='testchan', id_=0)
        self.mds.ChannelMetadata(title='testchan', id_=123)
        self.mds.ChannelMetadata(title='testchan', id_=0, public_key=unhexlify('0'*20),
                                 signature=unhexlify('0'*64), skip_key_check=True)
        self.mds.ChannelMetadata(title='testchan', id_=0, public_key=unhexlify('1'*20),
                                 signature=unhexlify('1'*64), skip_key_check=True)

        _ = [self.mds.TorrentMetadata(title='test' + str(x), status=NEW) for x in range(0, 3)]

        self.assertEqual(4, self.mds.get_num_channels())
        self.assertEqual(3, self.mds.get_num_torrents())
