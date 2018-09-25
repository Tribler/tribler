import os
from datetime import datetime

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateTorrentFileError, DuplicateChannelNameError
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


class TestChannelMetadata(TestAsServer):
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

    def setUpPreSession(self):
        super(TestChannelMetadata, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @staticmethod
    def get_sample_torrent_dict(my_key):
        """
        Utility method to return a dictionary with torrent information.
        """
        return {
            "infohash": buffer("1" * 20),
            "size": 123,
            "timestamp": datetime.utcnow(),
            "torrent_date": datetime.utcnow(),
            "tags": "bla",
            "tc_pointer": 123,
            "public_key": buffer(my_key.pub().key_to_bin()),
            "title": "lalala"
        }

    @staticmethod
    def get_sample_channel_dict(my_key):
        """
        Utility method to return a dictionary with a channel information.
        """
        return dict(TestChannelMetadata.get_sample_torrent_dict(my_key), votes=222, subscribed=False, version=1)

    @db_session
    def test_serialization(self):
        """
        Test converting channel metadata to serialized data
        """
        channel_metadata = self.session.lm.mds.ChannelMetadata.from_dict({})
        self.assertTrue(channel_metadata.serialized())

    @db_session
    def test_list_contents(self):
        """
        Test whether a correct list with channel content is returned from the database
        """
        pub_key1 = ECCrypto().generate_key('low').pub().key_to_bin()
        pub_key2 = ECCrypto().generate_key('low').pub().key_to_bin()

        channel1 = self.session.lm.mds.ChannelMetadata(public_key=pub_key1)
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, public_key=pub_key1))

        channel2 = self.session.lm.mds.ChannelMetadata(public_key=pub_key2)
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, public_key=pub_key2))
        self.session.lm.mds.TorrentMetadata.from_dict(dict(self.torrent_template, public_key=pub_key2))

        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(2, len(channel2.contents_list))

    def test_create_channel(self):
        """
        Test whether creating a channel works as expected
        """
        my_key = self.session.trustchain_keypair
        channel_metadata = self.session.lm.mds.ChannelMetadata.create_channel(my_key, 'test', 'test')
        self.assertTrue(channel_metadata)
        self.assertRaises(DuplicateChannelNameError,
                          self.session.lm.mds.ChannelMetadata.create_channel, my_key, 'test', 'test')

    @db_session
    def test_update_metadata(self):
        """
        Test whether metadata is correctly updated and signed
        """
        my_key = self.session.trustchain_keypair
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(my_key)
        channel_metadata = self.session.lm.mds.ChannelMetadata.from_dict(sample_channel_dict)
        self.session.lm.mds.TorrentMetadata.from_dict(self.torrent_template)
        update_dict = {
            "tc_pointer": 222,
            "tags": "eee",
            "title": "qqq"
        }
        channel_metadata.update_metadata(my_key, update_dict=update_dict)
        self.assertDictContainsSubset(update_dict, channel_metadata.to_dict())

    @db_session
    def test_process_channel_metadata_payload(self):
        """
        Test whether a channel metadata payload is processed correctly
        """
        payload = ChannelMetadataPayload.from_file(self.CHANNEL_METADATA)
        channel_metadata = self.session.lm.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertTrue(channel_metadata)

        # Check that we do not add it again
        self.session.lm.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertEqual(len(self.session.lm.mds.ChannelMetadata.select()), 1)

        # Check that we always take the latest version
        channel_metadata.version -= 1
        self.assertEqual(channel_metadata.version, 2)
        channel_metadata = self.session.lm.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertEqual(channel_metadata.version, 3)
        self.assertEqual(len(self.session.lm.mds.ChannelMetadata.select()), 1)

    @db_session
    def test_get_dirname(self):
        """
        Test whether the correct directory name is returned for channel metadata
        """
        my_key = self.session.trustchain_keypair
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(my_key)
        channel_metadata = self.session.lm.mds.ChannelMetadata.from_dict(sample_channel_dict)

        self.assertEqual(len(channel_metadata.dir_name), 60)

    @db_session
    def test_get_channel_with_id(self):
        """
        Test retrieving a channel with a specific ID
        """
        self.assertIsNone(self.session.lm.mds.ChannelMetadata.get_channel_with_id('a' * 20))
        channel_metadata = self.session.lm.mds.ChannelMetadata.create_channel(
            self.session.trustchain_keypair, 'test', 'test')
        self.assertIsNotNone(self.session.lm.mds.ChannelMetadata.get_channel_with_id(channel_metadata.public_key))

    @db_session
    def test_add_metadata_to_channel(self):
        """
        Test whether adding new torrents to a channel works as expected
        """
        my_key = self.session.trustchain_keypair
        channel_metadata = self.session.lm.mds.ChannelMetadata.create_channel(my_key, 'test', 'test')
        torrent1_metadata = self.session.lm.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, public_key=channel_metadata.public_key))
        channel_metadata.add_metadata_to_channel(my_key, self.session.lm.mds.channels_dir, [torrent1_metadata])

        self.assertEqual(channel_metadata.version, 2)
        self.assertEqual(channel_metadata.size, 1)

    @db_session
    def test_add_torrent_to_channel(self):
        """
        Test adding a torrent to your channel
        """
        my_key = self.session.trustchain_keypair
        channel_metadata = self.session.lm.mds.ChannelMetadata.create_channel(my_key, 'test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        channel_metadata.add_torrent_to_channel(my_key, tdef, None, self.session.lm.mds.channels_dir)
        self.assertTrue(channel_metadata.contents_list)
        self.assertRaises(DuplicateTorrentFileError, channel_metadata.add_torrent_to_channel,
                          my_key, tdef, None, self.session.lm.mds.channels_dir)

    @db_session
    def test_delete_torrent_from_channel(self):
        """
        Test deleting a torrent from your channel
        """
        my_key = self.session.trustchain_keypair
        channel_metadata = self.session.lm.mds.ChannelMetadata.create_channel(my_key, 'test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        channel_metadata.add_torrent_to_channel(my_key, tdef, None, self.session.lm.mds.channels_dir)

        old_infohash, new_infohash = channel_metadata.delete_torrent_from_channel(
            my_key, 'a' * 20, self.session.lm.mds.channels_dir)
        self.assertEqual(old_infohash, new_infohash)

        old_infohash, new_infohash = channel_metadata.delete_torrent_from_channel(
            my_key, tdef.get_infohash(), self.session.lm.mds.channels_dir)
        self.assertNotEqual(old_infohash, new_infohash)
        self.assertFalse(channel_metadata.contents_list)
