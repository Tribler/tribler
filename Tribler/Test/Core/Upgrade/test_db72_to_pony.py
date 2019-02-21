from __future__ import absolute_import

import os
import shutil
import sqlite3

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Upgrade.db72_to_pony import DispersyToPonyMigration, CONVERSION_FINISHED, \
    CONVERSION_FROM_72, old_db_version_ok, cleanup_pony_experimental_db, new_db_version_ok, already_upgraded, \
    should_upgrade
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto

OLD_DB_SAMPLE = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', 'data',
                             'upgrade_databases', 'tribler_v29.sdb')


class TestUpgradeDB72ToPony(TriblerCoreTest):
    @inlineCallbacks
    def setUp(self):
        yield super(TestUpgradeDB72ToPony, self).setUp()

        self.my_key = default_eccrypto.generate_key(u"curve25519")
        mds_db = os.path.join(self.session_base_dir, 'test.db')
        mds_channels_dir = self.session_base_dir

        self.mds = MetadataStore(mds_db, mds_channels_dir, self.my_key)
        self.m = DispersyToPonyMigration(OLD_DB_SAMPLE)
        self.m.initialize(self.mds)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestUpgradeDB72ToPony, self).tearDown()

    def test_get_personal_channel_title(self):
        self.assertTrue(self.m.personal_channel_title)

    def test_get_old_torrents_count(self):
        self.assertEqual(self.m.get_old_torrents_count(), 19)

    def test_get_personal_torrents_count(self):
        self.assertEqual(self.m.get_personal_channel_torrents_count(), 2)

    def test_convert_personal_channel(self):
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
        tr = self.mds.TrackerState(url="http://ipv6.torrent.ubuntu.com:6969/announce")
        self.m.update_trackers_info()
        self.assertEqual(tr.failures, 2)
        self.assertEqual(tr.alive, True)
        self.assertEqual(tr.last_check, 1548776649)


class TestUpgradePreconditionChecker(TriblerCoreTest):

    def test_old_db_version_check(self):
        # Correct old database
        self.assertTrue(old_db_version_ok(OLD_DB_SAMPLE))

        # Wrong old database version
        old_db = os.path.join(self.session_base_dir, 'old.db')
        shutil.copyfile(OLD_DB_SAMPLE, old_db)
        conn = sqlite3.connect(old_db)
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE MyInfo SET value = 28 WHERE entry == 'version'")
        self.assertFalse(old_db_version_ok(old_db))

    def test_cleanup_pony_experimental_db(self):
        # Create a Pony database of older experimental version
        pony_db = os.path.join(self.session_base_dir, 'pony.db')
        pony_db_bak = os.path.join(self.session_base_dir, 'pony2.db')
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        mds.shutdown()
        shutil.copyfile(pony_db, pony_db_bak)

        connection = sqlite3.connect(pony_db)
        with connection:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE MiscData")
        connection.close()

        # Assert older experimental version is deleted
        self.assertFalse(cleanup_pony_experimental_db(pony_db))
        self.assertFalse(os.path.exists(pony_db))

        # Assert recent database version is left untouched
        self.assertFalse(cleanup_pony_experimental_db(pony_db_bak))
        self.assertTrue(os.path.exists(pony_db_bak))

        # Assert True is returned for a garbled db and nothing is done with it
        garbled_db = os.path.join(self.session_base_dir, 'garbled.db')
        with open(garbled_db, 'w') as f:
            f.write("123")
        self.assertRaises(sqlite3.DatabaseError, cleanup_pony_experimental_db, garbled_db)
        self.assertTrue(os.path.exists(garbled_db))

    def test_new_db_version_ok(self):
        pony_db = os.path.join(self.session_base_dir, 'pony.db')
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        mds.shutdown()

        self.assertTrue(new_db_version_ok(pony_db))

        connection = sqlite3.connect(pony_db)
        with connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE MiscData SET value = 12313512 WHERE name == 'db_version'")
        self.assertFalse(new_db_version_ok(pony_db))

    def test_already_upgraded(self):
        pony_db = os.path.join(self.session_base_dir, 'pony.db')
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        mds.shutdown()

        self.assertFalse(already_upgraded(pony_db))

        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        with db_session:
            mds.MiscData(name=CONVERSION_FROM_72, value=CONVERSION_FINISHED)
        mds.shutdown()

        self.assertTrue(already_upgraded(pony_db))

    def test_should_upgrade(self):
        from Tribler.Core.Upgrade import db72_to_pony
        pony_db = os.path.join(self.session_base_dir, 'pony.db')

        # Old DB does not exist
        self.assertFalse(should_upgrade(os.path.join(self.session_base_dir, 'nonexistent.db'), None))

        # Old DB is not OK
        db72_to_pony.old_db_version_ok = lambda _: False
        self.assertFalse(should_upgrade(OLD_DB_SAMPLE, None))

        # Pony DB does not exist
        db72_to_pony.old_db_version_ok = lambda _: True
        self.assertTrue(should_upgrade(OLD_DB_SAMPLE, pony_db))


        mock_logger = MockObject()
        mock_logger.error = lambda _,a: None

        # Bad Pony DB
        with open(pony_db, 'w') as f:
            f.write("")
        self.assertFalse(should_upgrade(OLD_DB_SAMPLE, pony_db, logger=mock_logger))


