import os

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Upgrade.db72_to_pony import DispersyToPonyMigration
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestUpgradeDB72ToPony(TriblerCoreTest):
    OLD_DB_SAMPLE = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', 'data',
                                 'upgrade_databases', 'tribler_v29.sdb')

    @inlineCallbacks
    def setUp(self):
        yield super(TestUpgradeDB72ToPony, self).setUp()

        self.my_key = default_eccrypto.generate_key(u"curve25519")
        mds_db = os.path.join(self.session_base_dir, 'test.db')
        mds_channels_dir = self.session_base_dir

        self.mds = MetadataStore(mds_db, mds_channels_dir, self.my_key)
        self.m = DispersyToPonyMigration(self.OLD_DB_SAMPLE, self.mds)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestUpgradeDB72ToPony, self).tearDown()

    def test_get_personal_channel_title(self):
        self.m.initialize()
        self.assertTrue(self.m.personal_channel_title)

    def test_get_old_torrents_count(self):
        self.m.initialize()
        self.assertEqual(self.m.get_old_torrents_count(), 19)

    def test_get_personal_torrents_count(self):
        self.m.initialize()
        self.assertEqual(self.m.get_personal_channel_torrents_count(), 2)

    def test_convert_personal_channel(self):
        self.m.initialize()
        self.m.convert_personal_channel()
        my_channel = self.mds.ChannelMetadata.get_my_channel()
        self.assertEqual(len(my_channel.contents_list), 2)
        self.assertEqual(my_channel.num_entries, 2)
        for t in my_channel.contents_list:
            self.assertTrue(t.has_valid_signature())
        self.assertTrue(my_channel.has_valid_signature())
        self.assertEqual(self.m.personal_channel_title[:200], my_channel.title)

    @db_session
    def test_convert_all_channels(self):
        self.m.initialize()
        self.m.convert_discovered_torrents()
        self.m.convert_discovered_channels()
        chans = self.mds.ChannelMetadata.get_entries()

        self.assertEqual(len(chans[0]), 2)
        for c in chans[0]:
            self.assertNotEqual(self.m.personal_channel_title[:200], c.title)
            self.assertEqual(c.status, LEGACY_ENTRY)
            self.assertTrue(c.contents_list)
            for t in c.contents_list:
                self.assertEqual(t.status, LEGACY_ENTRY)

    @db_session
    def test_update_trackers(self):
        self.m.initialize()
        tr = self.mds.TrackerState(url="http://ipv6.torrent.ubuntu.com:6969/announce")
        self.m.update_trackers_info()
        self.assertEqual(tr.failures, 2)
        self.assertEqual(tr.alive, True)
        self.assertEqual(tr.last_check, 1548776649)
