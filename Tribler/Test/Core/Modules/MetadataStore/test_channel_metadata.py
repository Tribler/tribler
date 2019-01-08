from __future__ import absolute_import

import os
from datetime import datetime

from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import entries_to_chunk, CHANNEL_DIR_NAME_LENGTH, \
    ROOT_CHANNEL_ID
from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import NEW
from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateTorrentFileError, DuplicateChannelNameError
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.pyipv8.ipv8.database import database_blob
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestChannelMetadata(TriblerCoreTest):
    """
    Contains various tests for the channel metadata type.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
    CHANNEL_METADATA = os.path.join(DATA_DIR, 'sample_channel', 'channel.mdblob')

    @inlineCallbacks
    def setUp(self):
        yield super(TestChannelMetadata, self).setUp()
        self.torrent_template = {
            "title": "",
            "infohash": "",
            "torrent_date": datetime(1970, 1, 1),
            "tags": "video"
        }
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir,
                                 self.my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestChannelMetadata, self).tearDown()

    @staticmethod
    def get_sample_torrent_dict(my_key):
        """
        Utility method to return a dictionary with torrent information.
        """
        return {
            "infohash": database_blob("1" * 20),
            "size": 123,
            "torrent_date": datetime.utcnow(),
            "tags": "bla",
            "id_": 123,
            "public_key": database_blob(my_key.pub().key_to_bin()[10:]),
            "title": "lalala"
        }

    @staticmethod
    def get_sample_channel_dict(my_key):
        """
        Utility method to return a dictionary with a channel information.
        """
        return dict(TestChannelMetadata.get_sample_torrent_dict(my_key), votes=222, subscribed=False, timestamp=1)

    @db_session
    def test_serialization(self):
        """
        Test converting channel metadata to serialized data
        """
        channel_metadata = self.mds.ChannelMetadata.from_dict({})
        self.assertTrue(channel_metadata.serialized())

    @db_session
    def test_list_contents(self):
        """
        Test whether a correct list with channel content is returned from the database
        """
        self.mds.Metadata._my_key = default_eccrypto.generate_key('low')
        channel1 = self.mds.ChannelMetadata()
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template))

        self.mds.Metadata._my_key = default_eccrypto.generate_key('low')
        channel2 = self.mds.ChannelMetadata()
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template))

        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(2, len(channel2.contents_list))
        self.assertEqual(2, channel2.contents_len)

    @db_session
    def test_create_channel(self):
        """
        Test whether creating a channel works as expected
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')

        self.assertTrue(channel_metadata)
        self.assertRaises(DuplicateChannelNameError,
                          self.mds.ChannelMetadata.create_channel, 'test', 'test')

    @db_session
    def test_update_metadata(self):
        """
        Test whether metadata is correctly updated and signed
        """
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(self.my_key)
        channel_metadata = self.mds.ChannelMetadata.from_dict(sample_channel_dict)
        self.mds.TorrentMetadata.from_dict(self.torrent_template)
        update_dict = {
            "id_": 222,
            "tags": "eee",
            "title": "qqq"
        }
        channel_metadata.update_metadata(update_dict=update_dict)
        self.assertDictContainsSubset(update_dict, channel_metadata.to_dict())

    @db_session
    def test_process_channel_metadata_payload(self):
        """
        Test whether a channel metadata payload is processed correctly
        """
        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)
        channel_metadata = self.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertTrue(channel_metadata)

        # Check that we do not add it again
        self.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertEqual(len(self.mds.ChannelMetadata.select()), 1)

        # Check that we always take the latest version
        channel_metadata.timestamp -= 1
        self.assertEqual(channel_metadata.timestamp, 9)
        channel_metadata = self.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertEqual(channel_metadata.timestamp, 10)
        self.assertEqual(len(self.mds.ChannelMetadata.select()), 1)

    @db_session
    def test_get_dirname(self):
        """
        Test whether the correct directory name is returned for channel metadata
        """
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(self.my_key)
        channel_metadata = self.mds.ChannelMetadata.from_dict(sample_channel_dict)

        self.assertEqual(len(channel_metadata.dir_name), CHANNEL_DIR_NAME_LENGTH)

    @db_session
    def test_get_channel_with_dirname(self):
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(self.my_key)
        channel_metadata = self.mds.ChannelMetadata.from_dict(sample_channel_dict)
        dirname = channel_metadata.dir_name
        channel_result = self.mds.ChannelMetadata.get_channel_with_dirname(dirname)
        self.assertEqual(channel_metadata, channel_result)

    @db_session
    def test_get_channel_with_id(self):
        """
        Test retrieving a channel with a specific ID
        """
        self.assertIsNone(self.mds.ChannelMetadata.get_channel_with_id('a' * 20))
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        self.assertIsNotNone(self.mds.ChannelMetadata.get_channel_with_id(channel_metadata.public_key))

    @db_session
    def test_add_metadata_to_channel(self):
        """
        Test whether adding new torrents to a channel works as expected
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, public_key=channel_metadata.public_key, status=NEW))
        channel_metadata.commit_channel_torrent()

        self.assertEqual(channel_metadata.id_, ROOT_CHANNEL_ID)
        self.assertEqual(channel_metadata.timestamp, 3)
        self.assertEqual(channel_metadata.num_entries, 1)

    @db_session
    def test_add_torrent_to_channel(self):
        """
        Test adding a torrent to your channel
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        channel_metadata.add_torrent_to_channel(tdef, None)
        self.assertTrue(channel_metadata.contents_list)
        self.assertRaises(DuplicateTorrentFileError, channel_metadata.add_torrent_to_channel, tdef, None)

    @db_session
    def test_delete_torrent_from_channel(self):
        """
        Test deleting a torrent from your channel
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

        # Check that nothing is committed when deleting uncommited torrent metadata
        channel_metadata.add_torrent_to_channel(tdef, None)
        channel_metadata.delete_torrent_from_channel(tdef.get_infohash())
        self.assertEqual(0, len(channel_metadata.contents_list))

        # Check append-only deletion process
        channel_metadata.add_torrent_to_channel(tdef, None)
        channel_metadata.commit_channel_torrent()
        self.assertEqual(1, len(channel_metadata.contents_list))
        channel_metadata.delete_torrent_from_channel(tdef.get_infohash())
        channel_metadata.commit_channel_torrent()
        self.assertEqual(0, len(channel_metadata.contents_list))

    @db_session
    def test_consolidate_channel_torrent(self):
        """
        Test completely re-commit your channel
        """
        channel = self.mds.ChannelMetadata.create_channel('test', 'test')
        my_dir = os.path.abspath(os.path.join(self.mds.channels_dir, channel.dir_name))
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

        # 1st torrent
        channel.add_torrent_to_channel(tdef, None)
        channel.commit_channel_torrent()

        # 2nd torrent
        md = self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, public_key=channel.public_key, status=NEW))
        channel.commit_channel_torrent()

        # Delete entry
        channel.delete_torrent_from_channel(tdef.get_infohash())
        channel.commit_channel_torrent()

        self.assertEqual(1, len(channel.contents_list))
        self.assertEqual(3, len(os.listdir(my_dir)))
        channel.consolidate_channel_torrent()
        self.assertEqual(1, len(os.listdir(my_dir)))

    def test_mdblob_dont_fit_exception(self):
        with db_session:
            md_list = [self.mds.TorrentMetadata(title='test' + str(x)) for x in xrange(0, 1)]
        self.assertRaises(Exception, entries_to_chunk, md_list, chunk_size=1)
