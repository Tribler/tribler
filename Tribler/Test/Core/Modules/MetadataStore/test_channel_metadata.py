from __future__ import absolute_import

import os
import random
from binascii import unhexlify
from datetime import datetime
from time import sleep

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import (
    CHANNEL_DIR_NAME_LENGTH, ROOT_CHANNEL_ID, entries_to_chunk)
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW, TODELETE, UPDATED
from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload, REGULAR_TORRENT
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateChannelIdError, DuplicateTorrentFileError
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.common import TORRENT_UBUNTU_FILE


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
        self.mds = MetadataStore(":memory:", self.session_base_dir, self.my_key)

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
        channel_metadata = self.mds.ChannelMetadata.from_dict({"infohash": str(random.getrandbits(160))})
        self.assertTrue(channel_metadata.serialized())

    @db_session
    def test_list_contents(self):
        """
        Test whether a correct list with channel content is returned from the database
        """
        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel1 = self.mds.ChannelMetadata(infohash=str(random.getrandbits(160)))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, origin_id=channel1.id_))

        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel2 = self.mds.ChannelMetadata(infohash=str(random.getrandbits(160)))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash="1", origin_id=channel2.id_))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash="2", origin_id=channel2.id_))

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
        self.assertRaises(DuplicateChannelIdError,
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
        self.assertEqual(channel_metadata.timestamp, 1551110113006)
        channel_metadata = self.mds.ChannelMetadata.process_channel_metadata_payload(payload)
        self.assertEqual(channel_metadata.timestamp, 1551110113007)
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

        # Test for corner-case of channel PK starting with zeroes
        channel_metadata.public_key = database_blob(unhexlify('0' * 128))
        channel_result = self.mds.ChannelMetadata.get_channel_with_dirname(channel_metadata.dir_name)
        self.assertEqual(channel_metadata, channel_result)

    @db_session
    def test_add_metadata_to_channel(self):
        """
        Test whether adding new torrents to a channel works as expected
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        original_channel = channel_metadata.to_dict()
        md = self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, status=NEW))
        channel_metadata.commit_channel_torrent()

        self.assertEqual(channel_metadata.id_, ROOT_CHANNEL_ID)
        self.assertLess(original_channel["timestamp"], channel_metadata.timestamp)
        self.assertLess(md.timestamp, channel_metadata.timestamp)
        self.assertEqual(channel_metadata.num_entries, 1)

    @db_session
    def test_add_torrent_to_channel(self):
        """
        Test adding a torrent to your channel
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        channel_metadata.add_torrent_to_channel(tdef, {'description': 'blabla'})
        self.assertTrue(channel_metadata.contents_list)
        self.assertRaises(DuplicateTorrentFileError, channel_metadata.add_torrent_to_channel, tdef, None)

    @db_session
    def test_torrent_exists_in_channel(self):
        """
        Test torrent already exists in the channel.
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash="1"))
        self.assertTrue(channel_metadata.torrent_exists("1"))
        self.assertFalse(channel_metadata.torrent_exists("0"))

    @db_session
    def test_copy_to_channel(self):
        """
        Test copying a torrent from an another channel.
        """
        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel1 = self.mds.ChannelMetadata(infohash=str(random.getrandbits(160)))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash="1", origin_id=channel1.id_))

        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel2 = self.mds.ChannelMetadata(infohash=str(random.getrandbits(160)), id_=ROOT_CHANNEL_ID)

        # Trying copying existing torrent to channel
        new_torrent = channel2.copy_to_channel("1")
        self.assertIsNotNone(new_torrent)
        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(1, len(channel2.contents_list))

        # Try copying non-existing torrent ot channel
        new_torrent2 = channel2.copy_to_channel("2")
        self.assertIsNone(new_torrent2)
        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(1, len(channel2.contents_list))

    @db_session
    def test_restore_torrent_in_channel(self):
        """
        Test if the torrent scheduled for deletion is restored/updated after the user tries to re-add it.
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        md = channel_metadata.add_torrent_to_channel(tdef, None)

        # Check correct re-add
        md.status = TODELETE
        md_updated = channel_metadata.add_torrent_to_channel(tdef, None)
        self.assertEqual(UPDATED, md.status)
        self.assertEqual(md_updated, md)
        self.assertTrue(md.has_valid_signature)

        # Check update of torrent properties from a new tdef
        md.status = TODELETE
        new_tracker_address = u'http://tribler.org/announce'
        tdef.torrent_parameters['announce'] = new_tracker_address
        md_updated = channel_metadata.add_torrent_to_channel(tdef, None)
        self.assertEqual(md_updated, md)
        self.assertEqual(md.status, UPDATED)
        self.assertEqual(md.tracker_info, new_tracker_address)
        self.assertTrue(md.has_valid_signature)
        # In addition, check that the trackers table was properly updated
        self.assertEqual(len(md.health.trackers), 2)

    @db_session
    def test_delete_torrent_from_channel(self):
        """
        Test deleting a torrent from your channel
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

        # Check that nothing is committed when deleting uncommited torrent metadata
        channel_metadata.add_torrent_to_channel(tdef, None)
        channel_metadata.delete_torrent(tdef.get_infohash())
        self.assertEqual(0, len(channel_metadata.contents_list))

        # Check append-only deletion process
        channel_metadata.add_torrent_to_channel(tdef, None)
        channel_metadata.commit_channel_torrent()
        self.assertEqual(1, len(channel_metadata.contents_list))
        channel_metadata.delete_torrent(tdef.get_infohash())
        channel_metadata.commit_channel_torrent()
        self.assertEqual(0, len(channel_metadata.contents_list))

    @db_session
    def test_vsids(self):
        peer_key = default_eccrypto.generate_key(u"curve25519")
        self.assertEqual(1.0, self.mds.Vsids[0].bump_amount)

        channel = self.mds.ChannelMetadata.create_channel('test', 'test')
        self.mds.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
        self.mds.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
        sleep(0.1)  # Necessary mostly on Windows, because of the lower timer resolution
        self.assertLess(0.0, channel.votes)
        self.assertLess(1.0, self.mds.Vsids[0].bump_amount)

        # Make sure normalization for display purposes work
        self.assertAlmostEqual(channel.to_simple_dict()["votes"], 1.0)

        # Make sure the rescale works for the channels
        self.mds.Vsids[0].normalize()
        self.assertEqual(1.0, self.mds.Vsids[0].bump_amount)
        self.assertEqual(1.0, channel.votes)

    @db_session
    def test_commit_channel_torrent(self):
        channel = self.mds.ChannelMetadata.create_channel('test', 'test')
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        channel.add_torrent_to_channel(tdef, None)
        # The first run should return the infohash, the second should return None, because nothing was really done
        self.assertTrue(channel.commit_channel_torrent())
        self.assertFalse(channel.commit_channel_torrent())

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
        channel.delete_torrent(tdef.get_infohash())
        channel.commit_channel_torrent()

        self.assertEqual(1, len(channel.contents_list))
        self.assertEqual(3, len(os.listdir(my_dir)))
        channel.consolidate_channel_torrent()
        self.assertEqual(1, len(os.listdir(my_dir)))

    def test_mdblob_dont_fit_exception(self):
        with db_session:
            md_list = [self.mds.TorrentMetadata(title='test' + str(x), infohash=str(random.getrandbits(160))) for x in
                       xrange(0, 1)]
        self.assertRaises(Exception, entries_to_chunk, md_list, chunk_size=1)

    @db_session
    def test_get_channels(self):
        """
        Test whether we can get channels
        """

        # First we create a few channels
        for ind in xrange(10):
            self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
            _ = self.mds.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0),
                                         infohash=str(random.getrandbits(160)))
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=5)
        self.assertEqual(len(channels), 5)

        # Test filtering
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=5, query_filter='channel5')
        self.assertEqual(len(channels), 1)

        # Test sorting
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', sort_asc=False)
        self.assertEqual(len(channels), 10)
        self.assertEqual(channels[0].title, 'channel9')

        # Test fetching subscribed channels
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', subscribed=True)
        self.assertEqual(len(channels), 5)

    @db_session
    def test_get_channel_name(self):
        infohash = "\x00" * 20
        title = "testchan"
        chan = self.mds.ChannelMetadata(title=title, infohash=database_blob(infohash))
        dirname = chan.dir_name

        self.assertEqual(title, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))
        chan.infohash = "\x11" * 20
        self.assertEqual("OLD:" + title, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))
        chan.delete()
        self.assertEqual(dirname, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))

    @db_session
    def check_add(self, torrents_in_dir, errors, recursive):
        TEST_TORRENTS_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))),
                                         '..', '..', '..', 'data', 'linux_torrents')
        chan = self.mds.ChannelMetadata.create_channel(title='testchan')
        torrents, e = chan.add_torrents_from_dir(TEST_TORRENTS_DIR, recursive)
        self.assertEqual(torrents_in_dir, len(torrents))
        self.assertEqual(errors, len(e))
        with db_session:
            q = self.mds.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT)
            self.assertEqual(torrents_in_dir - len(e), q.count())

    def test_add_torrents_from_dir(self):
        self.check_add(9, 0, recursive=False)

    def test_add_torrents_from_dir_recursive(self):
        self.check_add(11, 1, recursive=True)
