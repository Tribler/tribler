import os
import shutil
from asyncio import Future
from pathlib import Path

from pony.orm import db_session

from tribler_common.simpledefs import NTFY, STATEDIR_CHANNELS_DIR, STATEDIR_CHECKPOINT_DIR, \
    STATEDIR_DB_DIR, STATEDIR_WALLET_DIR

from tribler_core import version
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.tests.tools.tools import timeout
from tribler_core.upgrade.upgrade import TriblerUpgrader, cleanup_noncompliant_channel_torrents
from tribler_core.upgrade.upgrade_base import AbstractUpgrader
from tribler_core.utilities.configparser import CallbackConfigParser
from tribler_core.utilities.path_util import str_path


class TestUpgrader(AbstractUpgrader):

    async def setUp(self):
        await super(TestUpgrader, self).setUp()
        self.upgrader = TriblerUpgrader(self.session)

    @timeout(10)
    async def test_update_status_text(self):
        test_future = Future()

        def on_upgrade_tick(status_text):
            self.assertEqual(status_text, "12345")
            test_future.set_result(None)

        self.session.notifier.add_observer(NTFY.UPGRADER_TICK, on_upgrade_tick)
        self.upgrader.update_status("12345")
        await test_future

    @timeout(10)
    async def test_upgrade_72_to_pony(self):
        OLD_DB_SAMPLE = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
        old_database_path = self.session.config.get_state_dir() / 'sqlite' / 'tribler.sdb'
        new_database_path = self.session.config.get_state_dir() / 'sqlite' / 'metadata.db'
        shutil.copyfile(OLD_DB_SAMPLE, old_database_path)

        await self.upgrader.run()
        channels_dir = self.session.config.get_chant_channels_dir()
        mds = MetadataStore(new_database_path, channels_dir, self.session.trustchain_keypair)
        with db_session:
            self.assertEqual(mds.TorrentMetadata.select().count(), 24)
        mds.shutdown()

    @timeout(10)
    async def test_upgrade_pony_db_6to7(self):
        """
        Test that channels and torrents with forbidden words are cleaned up during upgrade from Pony db ver 6 to 7.
        Also, check that the DB version is upgraded.
        :return:
        """
        OLD_DB_SAMPLE = TESTS_DATA_DIR / 'upgrade_databases' / 'pony_v6.db'
        old_database_path = self.session.config.get_state_dir() / 'sqlite' / 'metadata.db'
        shutil.copyfile(OLD_DB_SAMPLE, old_database_path)

        await self.upgrader.run()
        channels_dir = self.session.config.get_chant_channels_dir()
        mds = MetadataStore(old_database_path, channels_dir, self.session.trustchain_keypair)
        with db_session:
            self.assertEqual(mds.TorrentMetadata.select().count(), 23)
            self.assertEqual(mds.ChannelMetadata.select().count(), 2)
            self.assertEqual(int(mds.MiscData.get(name="db_version").value), 7)
        mds.shutdown()

    @timeout(10)
    async def test_skip_upgrade_72_to_pony(self):
        OLD_DB_SAMPLE = TESTS_DATA_DIR / 'upgrade_databases' / 'tribler_v29.sdb'
        old_database_path = self.session.config.get_state_dir() / 'sqlite' / 'tribler.sdb'
        new_database_path = self.session.config.get_state_dir() / 'sqlite' / 'metadata.db'
        channels_dir = self.session.config.get_chant_channels_dir()

        shutil.copyfile(OLD_DB_SAMPLE, old_database_path)

        self.upgrader.skip()
        await self.upgrader.run()
        mds = MetadataStore(new_database_path, channels_dir, self.session.trustchain_keypair)
        with db_session:
            self.assertEqual(mds.TorrentMetadata.select().count(), 0)
            self.assertEqual(mds.ChannelMetadata.select().count(), 0)
        mds.shutdown()

    def test_delete_noncompliant_state(self):
        STATE_DIR = TESTS_DATA_DIR / 'noncompliant_state_dir'
        tmpdir = self.temporary_directory() / STATE_DIR.name
        shutil.copytree(str_path(STATE_DIR), str_path(tmpdir))
        cleanup_noncompliant_channel_torrents(tmpdir)

        # Check cleanup of the channels dir
        dir_listing = list((tmpdir / "channels").iterdir())
        self.assertEqual(3, len(dir_listing))
        for f in (tmpdir / "channels").iterdir():
            self.assertEqual(CHANNEL_DIR_NAME_LENGTH, len(f.stem))

        # Check cleanup of torrent state dir
        checkpoints_dir = tmpdir / "dlcheckpoints"
        dir_listing = os.listdir(checkpoints_dir)
        self.assertEqual(1, len(dir_listing))
        file_path = checkpoints_dir / dir_listing[0]
        pstate = CallbackConfigParser()
        pstate.read_file(file_path)
        self.assertEqual(CHANNEL_DIR_NAME_LENGTH, len(pstate.get('state', 'metainfo')['info']['name']))


class TestUpgraderStateDirectory(AbstractUpgrader):

    async def setUp(self):
        await super(TestUpgraderStateDirectory, self).setUp()
        self.upgrader = TriblerUpgrader(self.session)
        self.original_version = version.version_id

    async def tearDown(self):
        version.version_id = self.original_version
        await super(TestUpgraderStateDirectory, self).tearDown()

    @timeout(10)
    async def test_state_directory_upgrade(self):
        """
        Test if a new state directory is created with proper files and directories on upgrade.
        """
        # Note that, the default version set in the code is 7.0.0-GIT.
        # So for the first time after running the (enabled) upgrader,
        # a new state directory for this version should be created.
        await self.upgrader.run()

        version_state_dir = self.session.config.get_state_dir(version_id=version.version_id)
        self.assertTrue(os.path.exists(version_state_dir))
        version_state_sub_dirs = os.listdir(version_state_dir)
        backup_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
        for backup_dir in backup_dirs:
            self.assertTrue(backup_dir in version_state_sub_dirs)

        # Creating keypairs to test that these key pairs are also copied
        self.upgrader.session.init_keypair()

        # Now lets increase the version and test that upgrader does backup the directory and copy proper files
        version.version_id = '100.100.100'

        # If the version backup is not enabled, upgrader will not try to create a backup of the previous state directory
        # and create a new state directory for the new version.
        self.session.config.set_version_backup_enabled(False)
        await self.upgrader.run()

        version_state_dir = Path(self.session.config.get_state_dir(version_id=version.version_id))
        self.assertFalse(os.path.exists(version_state_dir))

        self.session.config.set_version_backup_enabled(True)
        await self.upgrader.run()

        version_state_dir = Path(self.session.config.get_state_dir(version_id=version.version_id))
        self.assertTrue(os.path.exists(version_state_dir))
        version_state_sub_dirs = os.listdir(version_state_dir)
        backup_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
        for backup_dir in backup_dirs:
            self.assertTrue(backup_dir in version_state_sub_dirs)

        self.assertTrue(len(list(version_state_dir.glob("*.pem"))) > 1)
