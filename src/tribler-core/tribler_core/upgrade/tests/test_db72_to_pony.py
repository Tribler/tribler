import contextlib
import shutil
import sqlite3

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.modules.metadata_store.orm_bindings.channel_node import COMMITTED, LEGACY_ENTRY
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.upgrade.db72_to_pony import (
    CONVERSION_FINISHED,
    CONVERSION_FROM_72,
    CONVERSION_FROM_72_CHANNELS,
    CONVERSION_FROM_72_DISCOVERED,
    CONVERSION_FROM_72_PERSONAL,
    CONVERSION_STARTED,
    DispersyToPonyMigration,
    already_upgraded,
    cleanup_pony_experimental_db,
    new_db_version_ok,
    old_db_version_ok,
    should_upgrade,
)

OLD_DB_SAMPLE = TESTS_DATA_DIR / 'upgrade_databases/tribler_v29.sdb'


class TestUpgradeDB72ToPony(TriblerCoreTest):

    async def setUp(self):
        await super(TestUpgradeDB72ToPony, self).setUp()

        self.my_key = default_eccrypto.generate_key(u"curve25519")
        mds_db = self.session_base_dir / 'test.db'
        mds_channels_dir = self.session_base_dir

        self.mds = MetadataStore(mds_db, mds_channels_dir, self.my_key)
        self.m = DispersyToPonyMigration(OLD_DB_SAMPLE)
        self.m.initialize(self.mds)

    async def tearDown(self):
        self.mds.shutdown()
        await super(TestUpgradeDB72ToPony, self).tearDown()

    def test_get_personal_channel_title(self):
        self.assertTrue(self.m.personal_channel_title)

    def test_get_old_torrents_count(self):
        self.assertEqual(self.m.get_old_torrents_count(), 19)

    def test_get_personal_torrents_count(self):
        self.assertEqual(self.m.get_personal_channel_torrents_count(), 2)

    async def test_convert_personal_channel(self):
        async def check_channel():
            await self.m.convert_personal_channel()
            with db_session:
                my_channel = self.mds.ChannelMetadata.get_my_channels().first()

            self.assertEqual(len(my_channel.contents_list), 2)
            self.assertEqual(my_channel.num_entries, 2)
            for t in my_channel.contents_list:
                self.assertTrue(t.has_valid_signature())
            self.assertTrue(my_channel.has_valid_signature())
            self.assertEqual(self.m.personal_channel_title[:200], my_channel.title)

        await check_channel()

        # Now check the case where previous conversion of the personal channel had failed
        with db_session:
            self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_PERSONAL).value = CONVERSION_STARTED
        await check_channel()

    @db_session
    async def test_convert_legacy_channels(self):
        async def check_conversion():
            await self.m.convert_discovered_torrents()
            self.m.convert_discovered_channels()
            chans = self.mds.ChannelMetadata.get_entries()

            self.assertEqual(len(chans), 2)
            for c in chans:
                self.assertNotEqual(self.m.personal_channel_title[:200], c.title[:200])
                self.assertEqual(c.status, LEGACY_ENTRY)
                self.assertTrue(c.contents_list)
                for t in c.contents_list:
                    self.assertEqual(t.status, COMMITTED)
        await check_conversion()

        # Now check the case where the previous conversion failed at channels conversion
        with db_session:
            self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS).value = CONVERSION_STARTED
        await check_conversion()

        # Now check the case where the previous conversion stopped at torrents conversion
        with db_session:
            self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_CHANNELS).delete()
            self.mds.MiscData.get_for_update(name=CONVERSION_FROM_72_DISCOVERED).value = CONVERSION_STARTED
            for d in self.mds.TorrentMetadata.select()[:10][:10]:
                d.delete()
        await check_conversion()

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
        old_db = self.session_base_dir / 'old.db'
        shutil.copyfile(OLD_DB_SAMPLE, old_db)
        with contextlib.closing(sqlite3.connect(old_db)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE MyInfo SET value = 28 WHERE entry == 'version'")
        self.assertFalse(old_db_version_ok(old_db))

    def test_cleanup_pony_experimental_db(self):
        # Assert True is returned for a garbled db and nothing is done with it
        garbled_db = self.session_base_dir / 'garbled.db'
        with open(garbled_db, 'w') as f:
            f.write("123")
        self.assertRaises(sqlite3.DatabaseError, cleanup_pony_experimental_db, garbled_db)
        self.assertTrue(garbled_db.exists())

        # Create a Pony database of older experimental version
        pony_db = self.session_base_dir / 'pony.db'
        pony_db_bak = self.session_base_dir / 'pony2.db'
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        mds.shutdown()
        shutil.copyfile(pony_db, pony_db_bak)

        with contextlib.closing(sqlite3.connect(pony_db)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute("DROP TABLE MiscData")

        # Assert older experimental version is deleted
        cleanup_pony_experimental_db(pony_db)
        self.assertFalse(pony_db.exists())

        # Assert recent database version is left untouched
        cleanup_pony_experimental_db(pony_db_bak)
        self.assertTrue(pony_db_bak.exists())

    def test_new_db_version_ok(self):
        pony_db = self.session_base_dir / 'pony.db'
        my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(pony_db, self.session_base_dir, my_key)
        mds.shutdown()

        # Correct new dabatase
        self.assertTrue(new_db_version_ok(pony_db))
        
        # Wrong new database version
        with contextlib.closing(sqlite3.connect(pony_db)) as connection, connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE MiscData SET value = 12313512 WHERE name == 'db_version'")
        self.assertFalse(new_db_version_ok(pony_db))

    def test_already_upgraded(self):
        pony_db = self.session_base_dir / 'pony.db'
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
        from tribler_core.upgrade import db72_to_pony
        pony_db = self.session_base_dir / 'pony.db'

        # Old DB does not exist
        self.assertFalse(should_upgrade(self.session_base_dir / 'nonexistent.db', None))

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
