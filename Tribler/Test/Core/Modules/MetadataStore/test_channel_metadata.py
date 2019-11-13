from __future__ import absolute_import

import os
from binascii import unhexlify
from datetime import datetime
from itertools import combinations
from time import sleep

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import ObjectNotFound, db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH, entries_to_chunk
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED, NEW, TODELETE, UPDATED
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Core.exceptions import DuplicateTorrentFileError
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
        self.torrent_template = {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}
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
            "infohash": database_blob(b"1" * 20),
            "size": 123,
            "torrent_date": datetime.utcnow(),
            "tags": "bla",
            "id_": 123,
            "public_key": database_blob(my_key.pub().key_to_bin()[10:]),
            "title": "lalala",
        }

    @db_session
    def create_ext_chan(self, ext_key):
        src_chan = self.mds.ChannelMetadata(sign_with=ext_key, title="bla", infohash=random_infohash())
        self.mds.TorrentMetadata(origin_id=src_chan.id_, sign_with=ext_key, infohash=random_infohash())
        l2_coll1 = self.mds.CollectionNode(origin_id=src_chan.id_, sign_with=ext_key, title="bla-l2-1")
        self.mds.TorrentMetadata(origin_id=l2_coll1.id_, sign_with=ext_key, infohash=random_infohash())
        self.mds.TorrentMetadata(origin_id=l2_coll1.id_, sign_with=ext_key, infohash=random_infohash())
        l2_coll2 = self.mds.CollectionNode(origin_id=src_chan.id_, sign_with=ext_key, title="bla-l2-2")
        self.mds.TorrentMetadata(origin_id=l2_coll2.id_, sign_with=ext_key, infohash=random_infohash())
        self.mds.TorrentMetadata(origin_id=l2_coll2.id_, sign_with=ext_key, infohash=random_infohash())
        return src_chan

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
        channel_metadata = self.mds.ChannelMetadata.from_dict({"infohash": os.urandom(20)})
        self.assertTrue(channel_metadata.serialized())

    @db_session
    def test_list_contents(self):
        """
        Test whether a correct list with channel content is returned from the database
        """
        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel1 = self.mds.ChannelMetadata(infohash=os.urandom(20))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, origin_id=channel1.id_))

        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel2 = self.mds.ChannelMetadata(infohash=os.urandom(20))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash=b"1", origin_id=channel2.id_))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash=b"2", origin_id=channel2.id_))

        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(2, len(channel2.contents_list))
        self.assertEqual(2, channel2.contents_len)

    @db_session
    def test_get_dirname(self):
        """
        Test whether the correct directory name is returned for channel metadata
        """
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(self.my_key)
        channel_metadata = self.mds.ChannelMetadata.from_dict(sample_channel_dict)

        self.assertEqual(len(channel_metadata.dirname), CHANNEL_DIR_NAME_LENGTH)

    @db_session
    def test_get_channel_with_dirname(self):
        sample_channel_dict = TestChannelMetadata.get_sample_channel_dict(self.my_key)
        channel_metadata = self.mds.ChannelMetadata.from_dict(sample_channel_dict)
        dirname = channel_metadata.dirname
        channel_result = self.mds.ChannelMetadata.get_channel_with_dirname(dirname)
        self.assertEqual(channel_metadata, channel_result)

        # Test for corner-case of channel PK starting with zeroes
        channel_metadata.public_key = database_blob(unhexlify('0' * 128))
        channel_result = self.mds.ChannelMetadata.get_channel_with_dirname(channel_metadata.dirname)
        self.assertEqual(channel_metadata, channel_result)

    @db_session
    def test_add_metadata_to_channel(self):
        """
        Test whether adding new torrents to a channel works as expected
        """
        channel_metadata = self.mds.ChannelMetadata.create_channel('test', 'test')
        original_channel = channel_metadata.to_dict()
        md = self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, status=NEW, origin_id=channel_metadata.id_))
        channel_metadata.commit_channel_torrent()

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
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash=b"1"))
        self.assertTrue(channel_metadata.torrent_exists(b"1"))
        self.assertFalse(channel_metadata.torrent_exists(b"0"))

    @db_session
    def test_copy_to_channel(self):
        """
        Test copying a torrent from an another channel.
        """
        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel1 = self.mds.ChannelMetadata(infohash=os.urandom(20))
        self.mds.TorrentMetadata.from_dict(dict(self.torrent_template, infohash=b"1", origin_id=channel1.id_))

        self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
        channel2 = self.mds.ChannelMetadata(infohash=os.urandom(20))

        # Trying copying existing torrent to channel
        new_torrent = channel2.copy_torrent_from_infohash(b"1")
        self.assertIsNotNone(new_torrent)
        self.assertEqual(1, len(channel1.contents_list))
        self.assertEqual(1, len(channel2.contents_list))

        # Try copying non-existing torrent ot channel
        new_torrent2 = channel2.copy_torrent_from_infohash(b"2")
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
        tdef.torrent_parameters[b'announce'] = new_tracker_address.encode('utf-8')
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
        torrent = channel_metadata.add_torrent_to_channel(tdef, None)
        torrent.soft_delete()
        self.assertEqual(0, len(channel_metadata.contents_list))

        # Check append-only deletion process
        torrent = channel_metadata.add_torrent_to_channel(tdef, None)
        channel_metadata.commit_channel_torrent()
        self.assertEqual(1, len(channel_metadata.contents_list))
        torrent.soft_delete()
        channel_metadata.commit_channel_torrent()
        self.assertEqual(0, len(channel_metadata.contents_list))

    @db_session
    def test_vsids(self):
        """
        Test VSIDS-based channel popularity system.
        """
        peer_key = default_eccrypto.generate_key(u"curve25519")
        self.assertEqual(1.0, self.mds.Vsids[0].bump_amount)

        channel = self.mds.ChannelMetadata.create_channel('test', 'test')
        self.mds.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
        sleep(0.1)  # Necessary mostly on Windows, because of the lower timer resolution
        self.mds.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
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
    def test_recursive_commit_channel_torrent(self):
        status_types = [NEW, UPDATED, TODELETE, COMMITTED]

        def all_status_combinations():
            result = []
            for card in range(0, len(status_types) + 1):
                result.extend(list(combinations(status_types, card)))
            return result

        def generate_collection(parent, collection_status, contents_statuses, recurse=False):
            chan = self.mds.CollectionNode(
                title=parent.title + '->child_new_nonempty', origin_id=parent.id_, status=collection_status
            )
            for s in contents_statuses:
                self.mds.TorrentMetadata(infohash=random_infohash(), origin_id=chan.id_, status=s)
                if recurse:
                    for status in status_types:
                        generate_collection(chan, status, [NEW])
            return chan

        def generate_channel(recurse=False, status=NEW):
            toplevel_channel = self.mds.ChannelMetadata.create_channel('root', 'test')
            toplevel_channel.status = status
            for s in status_types:
                self.mds.TorrentMetadata(infohash=random_infohash(), origin_id=toplevel_channel.id_, status=s)
                if recurse:
                    for status_combination in all_status_combinations():
                        generate_collection(toplevel_channel, s, status_combination, recurse=recurse)
            return toplevel_channel

        # Make sure running commit on empty channels produces no error
        self.mds.CollectionNode.commit_all_channels()

        # All types of non-empty and empty toplevel channels
        for s in status_types:
            empty_chan = self.mds.ChannelMetadata.create_channel('root', 'test')
            empty_chan.status = s
            generate_channel(status=s)

        # A committed channel with a single deleted collection in it. It should not be deleted
        single_del_cont_chan = self.mds.ChannelMetadata.create_channel('root', 'test')
        self.mds.CollectionNode(status=TODELETE, origin_id=single_del_cont_chan.id_)

        # Create some orphaned MDs
        chan = generate_channel()
        orphaned_contents_rowids = [c.rowid for c in chan.get_contents_recursive()]
        self.mds.ChannelNode.delete(chan)  # We use it to delete non-recursively

        # Create a top-level collection node
        coll = self.mds.CollectionNode(origin_id=0, status=NEW)
        generate_collection(coll, NEW, [NEW, UPDATED, TODELETE])

        commit_results = self.mds.CollectionNode.commit_all_channels()
        # Check that commit results in the correct number of torrents produced
        self.assertEqual(4, len(commit_results))
        # Check that top-level collection node, while not committed to disk, still has its num_entries recalculated
        self.assertEqual(coll.num_entries, 2)
        # Check that all orphaned entries are deleted during commit
        self.assertFalse(self.mds.ChannelNode.exists(lambda g: g.rowid in orphaned_contents_rowids))

        # Create a single nested channel
        chan = generate_channel(recurse=True)

        chan.commit_channel_torrent()
        chan.local_version = 0
        len(chan.get_contents_recursive())

        chan.consolidate_channel_torrent()
        # Remove the channel and read it back from disk
        for c in chan.contents:
            c.delete()
        my_dir = os.path.abspath(os.path.join(self.mds.channels_dir, chan.dirname))
        self.mds.process_channel_dir(my_dir, chan.public_key, chan.id_, skip_personal_metadata_payload=False)
        self.assertEqual(chan.num_entries, 363)

    @db_session
    def test_consolidate_channel_torrent(self):
        """
        Test completely re-commit your channel
        """
        channel = self.mds.ChannelMetadata.create_channel('test', 'test')
        my_dir = os.path.abspath(os.path.join(self.mds.channels_dir, channel.dirname))
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

        # 1st torrent
        torrent_entry = channel.add_torrent_to_channel(tdef, None)
        channel.commit_channel_torrent()

        # 2nd torrent
        self.mds.TorrentMetadata.from_dict(
            dict(self.torrent_template, public_key=channel.public_key, origin_id=channel.id_, status=NEW)
        )
        channel.commit_channel_torrent()
        # Delete entry
        torrent_entry.soft_delete()
        channel.commit_channel_torrent()

        self.assertEqual(1, len(channel.contents_list))
        self.assertEqual(3, len(os.listdir(my_dir)))

        torrent3 = self.mds.TorrentMetadata(
            public_key=channel.public_key, origin_id=channel.id_, status=NEW, infohash=random_infohash()
        )
        channel.commit_channel_torrent()
        torrent3.soft_delete()

        channel.consolidate_channel_torrent()
        self.assertEqual(1, len(os.listdir(my_dir)))
        self.mds.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT).delete()
        channel.local_version = 0
        self.mds.process_channel_dir(my_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False)
        self.assertEqual(len(channel.contents[:]), 1)

    def test_mdblob_dont_fit_exception(self):
        with db_session:
            md_list = [self.mds.TorrentMetadata(title='test' + str(x), infohash=os.urandom(20)) for x in xrange(0, 1)]
        self.assertRaises(Exception, entries_to_chunk, md_list, chunk_size=1)

    @db_session
    def test_get_channels(self):
        """
        Test whether we can get channels
        """

        # First we create a few channels
        for ind in xrange(10):
            self.mds.ChannelNode._my_key = default_eccrypto.generate_key('low')
            self.mds.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0), infohash=os.urandom(20))
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=5)
        self.assertEqual(len(channels), 5)

        # Test filtering
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=5, query_filter='channel5')
        self.assertEqual(len(channels), 1)

        # Test sorting
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', sort_desc=True)
        self.assertEqual(len(channels), 10)
        self.assertEqual(channels[0].title, 'channel9')

        # Test fetching subscribed channels
        channels = self.mds.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', subscribed=True)
        self.assertEqual(len(channels), 5)

    @db_session
    def test_get_channel_name(self):
        """
        Test getting torrent name for a channel to be displayed in the downloads list
        """
        infohash = b"\x00" * 20
        title = "testchan"
        chan = self.mds.ChannelMetadata(title=title, infohash=database_blob(infohash))
        dirname = chan.dirname

        self.assertEqual(title, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))
        chan.infohash = b"\x11" * 20
        self.assertEqual("OLD:" + title, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))
        chan.delete()
        self.assertEqual(dirname, self.mds.ChannelMetadata.get_channel_name(dirname, infohash))

    @db_session
    def check_add(self, torrents_in_dir, errors, recursive):
        TEST_TORRENTS_DIR = os.path.join(
            os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', '..', 'data', 'linux_torrents'
        )
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

    @db_session
    def test_make_copy(self):
        """
        Test copying if recursive copying an external channel to a personal channel works as expected
        """
        src_chan = self.create_ext_chan(default_eccrypto.generate_key(u"curve25519"))

        tgt_chan = self.mds.ChannelMetadata(title='our chan', infohash=random_infohash(), status=NEW)
        src_chan.make_copy(tgt_chan.id_)
        src_chan.pprint_tree()
        tgt_chan.pprint_tree()
        copy = self.mds.CollectionNode.get(public_key=tgt_chan.public_key, origin_id=tgt_chan.id_)
        self.assertEqual("bla", copy.title)
        self.assertEqual(1 + len(src_chan.get_contents_recursive()), len(tgt_chan.get_contents_recursive()))

    @db_session
    def test_update_properties_move(self):
        """
        Test moving a Channel/Collection into another Channel/Collection or at the top of channel hierachy.
        """
        src_chan = self.create_ext_chan(self.mds.ChannelMetadata._my_key)
        src_chan_contents = src_chan.get_contents_recursive()
        tgt_chan = self.mds.ChannelMetadata.create_channel('dstchan')

        # Move channel into another channel so it becomes a collection
        result_chan = src_chan.update_properties({'origin_id': tgt_chan.id_})
        # Assert the moved channel changed type to collection
        self.assertEqual(type(result_chan), self.mds.CollectionNode)
        self.assertEqual(result_chan.metadata_type, COLLECTION_NODE)
        self.assertEqual(1 + len(src_chan_contents), len(tgt_chan.get_contents_recursive()))

        # Move collection to top level so it become a channel
        result_chan = result_chan.update_properties({'origin_id': 0})
        # Assert the move collection changed type to channel
        self.assertEqual(type(result_chan), self.mds.ChannelMetadata)
        self.assertEqual(result_chan.metadata_type, CHANNEL_TORRENT)

    @db_session
    def test_delete_recursive(self):
        """
        Test deleting channel and its contents recursively
        """
        src_chan = self.create_ext_chan(default_eccrypto.generate_key(u"curve25519"))
        src_chan.delete()
        self.assertEqual(0, self.mds.ChannelNode.select().count())

        src_chan = self.create_ext_chan(default_eccrypto.generate_key(u"curve25519"))
        src_chan_rowid = src_chan.rowid
        src_chan.delete(recursive=False)
        self.assertEqual(7, self.mds.ChannelNode.select().count())
        self.assertRaises(ObjectNotFound, self.mds.ChannelNode.__getitem__, src_chan_rowid)

    @db_session
    def test_get_parent_ids(self):
        """
        Test the routine that gets the full set (path) of a node's predecessors in the channels tree
        """
        src_chan = self.create_ext_chan(default_eccrypto.generate_key(u"curve25519"))
        coll1 = self.mds.CollectionNode.select(lambda g: g.origin_id == src_chan.id_).first()
        self.assertEqual((0, src_chan.id_, coll1.id_), coll1.contents.first().get_parents_ids())

        loop = self.mds.CollectionNode(id_=777, origin_id=777)
        self.assertNotIn(0, loop.get_parents_ids())
