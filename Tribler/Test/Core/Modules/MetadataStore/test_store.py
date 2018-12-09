from __future__ import absolute_import
import os
from datetime import datetime

from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import entries_to_chunk
from Tribler.Core.Modules.MetadataStore.serialization import (ChannelMetadataPayload, MetadataPayload,
                                                              UnknownBlobTypeException)
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


def make_wrong_payload(filename):
    key = default_eccrypto.generate_key(u"curve25519")
    metadata_payload = MetadataPayload(666, database_blob(key.pub().key_to_bin()), datetime.utcnow(), 123)
    with open(filename, 'wb') as output_file:
        output_file.write(''.join(metadata_payload.serialized(key)))


class TestMetadataStore(TriblerCoreTest):
    """
    This class contains tests for the metadata store.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    CHANNEL_DIR = os.path.join(DATA_DIR, 'sample_channel',
                               'd24941643ff471e40d7761c71f4e3a4c21a4a5e89b0281430d01e78a4e46')
    CHANNEL_METADATA = os.path.join(DATA_DIR, 'sample_channel', 'channel.mdblob')

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadataStore, self).setUp()
        my_key = default_eccrypto.generate_key(u"curve25519")

        self.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir,
                                 my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestMetadataStore, self).tearDown()

    @db_session
    def test_process_channel_dir_file(self):
        """
        Test whether we are able to process files in a directory containing torrent metadata
        """

        test_torrent_metadata = self.mds.TorrentMetadata(title='test')
        metadata_path = os.path.join(self.session_base_dir, 'metadata.data')
        test_torrent_metadata.to_file(metadata_path)
        # We delete this TorrentMeta info now, it should be added again to the database when loading it
        test_torrent_metadata.delete()
        loaded_metadata = self.mds.process_mdblob_file(metadata_path)
        self.assertEqual(loaded_metadata[0].title, 'test')

        # Test whether we delete existing metadata when loading a DeletedMetadata blob
        metadata = self.mds.TorrentMetadata(infohash='1' * 20)
        metadata.to_delete_file(metadata_path)
        loaded_metadata = self.mds.process_mdblob_file(metadata_path)
        # Make sure the original metadata is deleted
        self.assertListEqual(loaded_metadata, [])
        self.assertIsNone(self.mds.TorrentMetadata.get(infohash='1' * 20))

        # Test an unknown metadata type, this should raise an exception
        invalid_metadata = os.path.join(self.session_base_dir, 'invalidtype.mdblob')
        make_wrong_payload(invalid_metadata)
        self.assertRaises(UnknownBlobTypeException, self.mds.process_mdblob_file, invalid_metadata)

    @db_session
    def test_squash_mdblobs(self):
        chunk_size = self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT
        md_list = [self.mds.TorrentMetadata(title='test' + str(x)) for x in xrange(0, 10)]
        chunk, _ = entries_to_chunk(md_list, chunk_size=chunk_size)
        self.assertItemsEqual(md_list, self.mds.process_squashed_mdblob(chunk))

        # Test splitting into multiple chunks
        chunk, index = entries_to_chunk(md_list, chunk_size=1000)
        chunk += entries_to_chunk(md_list, chunk_size=1000, start_index=index)[0]
        self.assertItemsEqual(md_list, self.mds.process_squashed_mdblob(chunk))

    @db_session
    def test_multiple_squashed_commit_and_read(self):
        """
        Test committing entries into several squashed blobs and reading them back
        """
        self.mds.ChannelMetadata._CHUNK_SIZE_LIMIT = 500

        num_entries = 10
        channel = self.mds.ChannelMetadata(title='testchan')
        md_list = [self.mds.TorrentMetadata(title='test' + str(x)) for x in xrange(0, num_entries)]
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
        self.assertEqual(channel.local_version, 3)
