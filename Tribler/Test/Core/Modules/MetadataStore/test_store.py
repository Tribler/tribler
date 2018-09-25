import os

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.Modules.MetadataStore.store import MetadataStore, UnknownBlobTypeException
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto


class TestMetadataStore(TriblerCoreTest):
    """
    This class contains tests for the metadata store.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    CHANNEL_DIR = os.path.join(DATA_DIR, 'sample_channel',
                               'ab624893dc43e8e5488ff6589d9ad6df764c2ff12aea93e6741b91cca03f')
    CHANNEL_METADATA = os.path.join(DATA_DIR, 'sample_channel', 'channel.mdblob')

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadataStore, self).setUp()

        self.metadata_store = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir)

    @inlineCallbacks
    def tearDown(self):
        self.metadata_store.shutdown()
        yield super(TestMetadataStore, self).tearDown()

    @db_session
    def test_process_channel_dir_file(self):
        """
        Test whether we are able to process files in a directory containing torrent metadata
        """
        my_key = ECCrypto().generate_key(u"curve25519")
        pub_key_bin = my_key.pub().key_to_bin()

        test_torrent_metadata = self.metadata_store.TorrentMetadata(title='test', public_key=pub_key_bin)
        test_torrent_metadata.sign(my_key)
        metadata_path = os.path.join(self.session_base_dir, 'metadata.data')
        test_torrent_metadata.to_file(metadata_path)

        # We should get the existing TorrentMetadata object now
        loaded_metadata = self.metadata_store.process_channel_dir_file(metadata_path)
        self.assertEqual(loaded_metadata.title, 'test')

        # We delete this TorrentMeta info now, it should be added again to the database when loading it
        test_torrent_metadata.delete()
        loaded_metadata = self.metadata_store.process_channel_dir_file(metadata_path)
        self.assertEqual(loaded_metadata.title, 'test')

        # Test whether we delete existing metadata when loading a DeletedMetadata blob
        self.metadata_store.ChannelMetadata(version=1337, signature='c' * 64)
        deleted_metadata = self.metadata_store.DeletedMetadata(delete_signature='c' * 64, public_key=pub_key_bin)
        deleted_metadata.sign(my_key)
        deleted_metadata.to_file(metadata_path)
        loaded_metadata = self.metadata_store.process_channel_dir_file(metadata_path)
        self.assertIsNone(loaded_metadata)

        # Test an unknown metadata type, this should raise an exception
        invalid_metadata_path = os.path.join(TESTS_DATA_DIR, 'invalidtype.mdblob')
        self.assertRaises(UnknownBlobTypeException, self.metadata_store.process_channel_dir_file, invalid_metadata_path)

    def test_process_channel_dir(self):
        """
        Test processing a directory containing metadata blobs
        """
        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)
        channel_metadata = self.metadata_store.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertFalse(channel_metadata.contents_list)
        self.metadata_store.process_channel_dir(self.CHANNEL_DIR)
        self.assertEqual(len(channel_metadata.contents_list), 2)
