import logging
import os
import shutil
from configparser import MissingSectionHeaderError, ParsingError

from pony.orm import db_session

from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_CHECKPOINT_DIR,
    STATEDIR_DB_DIR,
    STATEDIR_WALLET_DIR,
)

from tribler_core.modules.category_filter.l2_filter import is_forbidden
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.upgrade.config_converter import convert_config_to_tribler74, convert_config_to_tribler75
from tribler_core.upgrade.db72_to_pony import DispersyToPonyMigration, cleanup_pony_experimental_db, should_upgrade
from tribler_core.utilities.configparser import CallbackConfigParser
from tribler_core.utilities.osutils import dir_copy
from tribler_core.version import version_id


def cleanup_noncompliant_channel_torrents(state_dir):
    logger = logging.getLogger(__name__)
    channels_dir = state_dir / "channels"
    # Remove torrents contents
    if channels_dir.exists():
        for d in channels_dir.iterdir():
            if len(d.stem) != CHANNEL_DIR_NAME_LENGTH:
                dir_path = channels_dir / d
                # We remove both malformed channel dirs and .torrent and .mdblob files for personal channel
                if dir_path.is_dir():
                    shutil.rmtree(str(dir_path), ignore_errors=True)
                elif dir_path.is_file():
                    os.unlink(str(dir_path))

    # Remove .state torrent resume files
    resume_dir = state_dir / "dlcheckpoints"
    if resume_dir.exists():
        for f in resume_dir.iterdir():
            if not str(f).endswith('.state'):
                continue
            file_path = resume_dir / f
            pstate = CallbackConfigParser()
            try:
                pstate.read_file(file_path)
            except (ParsingError, MissingSectionHeaderError):
                logger.warning("Parsing channel torrent resume file %s failed, deleting", file_path)
                os.unlink(file_path)
                continue

            if pstate and pstate.has_option('download_defaults', 'channel_download') and \
                    pstate.get('download_defaults', 'channel_download'):
                try:
                    name = pstate.get('state', 'metainfo')['info']['name']
                    if name and len(name) != CHANNEL_DIR_NAME_LENGTH:
                        os.unlink(file_path)
                except (TypeError, KeyError, ValueError):
                    logger.debug("Malfored .pstate file %s found during cleanup of non-compliant channel torrents.",
                                 file_path)


class TriblerUpgrader(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        self.notified = False
        self.failed = True

        self._dtp72 = None
        self.skip_upgrade_called = False

    def skip(self):
        self.skip_upgrade_called = True
        if self._dtp72:
            self._dtp72.shutting_down = True

    async def run(self):
        """
        Run the upgrader if it is enabled in the config.

        Note that by default, upgrading is enabled in the config. It is then disabled
        after upgrading to Tribler 7.
        """
        await self.upgrade_72_to_pony()
        await self.upgrade_pony_db_6to7()
        convert_config_to_tribler74()
        convert_config_to_tribler75()
        self.backup_state_directory()

    async def upgrade_pony_db_6to7(self):
        """
        Upgrade GigaChannel DB from version 6 (7.3.0) to version 7 (7.3.1).
        Migration should be relatively fast, so we do it in the foreground, without notifying the user
        and breaking it in smaller chunks as we do with 72_to_pony.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.session.config.get_state_dir() / 'sqlite' / 'metadata.db'
        channels_dir = self.session.config.get_chant_channels_dir()
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, channels_dir, self.session.trustchain_keypair, disable_sync=True)
        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != 6:
                return
            for c in mds.ChannelMetadata.select():
                if is_forbidden(c.title+c.tags):
                    c.contents.delete()
                    c.delete()
                    # The channel torrent will be removed by GigaChannel manager during the cruft cleanup

        # The process is broken down into batches to limit memory usage
        batch_size = 10000
        with db_session:
            total_entries = mds.TorrentMetadata.select().count()
            page_num = total_entries // batch_size
        while page_num >= 0:
            with db_session:
                for t in mds.TorrentMetadata.select().page(page_num, pagesize=batch_size):
                    if is_forbidden(t.title+t.tags):
                        t.delete()
            page_num -= 1
        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(7)
        mds.shutdown()
        return

    def update_status(self, status_text):
        self.session.notifier.notify(NTFY.UPGRADER_TICK, status_text)

    async def upgrade_72_to_pony(self):
        old_database_path = self.session.config.get_state_dir() / 'sqlite' / 'tribler.sdb'
        new_database_path = self.session.config.get_state_dir() / 'sqlite' / 'metadata.db'
        channels_dir = self.session.config.get_chant_channels_dir()

        if new_database_path.exists():
            cleanup_pony_experimental_db(str(new_database_path))
            cleanup_noncompliant_channel_torrents(self.session.config.get_state_dir())

        self._dtp72 = DispersyToPonyMigration(old_database_path, self.update_status, logger=self._logger)
        if not should_upgrade(old_database_path, new_database_path, logger=self._logger):
            self._dtp72 = None
            return
        # This thing is here mostly for the skip upgrade test to work...
        self._dtp72.shutting_down = self.skip_upgrade_called
        self.notify_starting()
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        mds = MetadataStore(new_database_path, channels_dir, self.session.trustchain_keypair, disable_sync=True)
        self._dtp72.initialize(mds)

        try:
            await self._dtp72.do_migration()
        except Exception as e:
            self._logger.error("Error in Upgrader callback chain: %s", e)
            return
        mds.shutdown()
        self.notify_done()

    def backup_state_directory(self):
        """
        Backs up the current state directory if the version in the state directory and in the code is different.
        """
        if self.session.config.get_version_backup_enabled() and self.session.config.get_version() \
                and not self.session.config.get_version() == version_id:

            src_state_dir = self.session.config.get_state_dir()
            dest_state_dir = self.session.config.get_state_dir(version=self.session.config.get_version())

            # If only there is no tribler config already in the backup directory, then make the current version backup.
            dest_conf_path = dest_state_dir / 'triblerd.conf'
            if not dest_conf_path.exists():
                # Backup selected directories
                backup_dirs = [STATEDIR_DB_DIR, STATEDIR_CHECKPOINT_DIR, STATEDIR_WALLET_DIR, STATEDIR_CHANNELS_DIR]
                src_sub_dirs = os.listdir(src_state_dir)
                for backup_dir in backup_dirs:
                    if backup_dir in src_sub_dirs:
                        dir_copy(src_state_dir / backup_dir, dest_state_dir / backup_dir)
                    else:
                        os.makedirs(dest_state_dir / backup_dir)

                # Backup keys and config files
                backup_files = ['ec_multichain.pem', 'ecpub_multichain.pem', 'ec_trustchain_testnet.pem',
                                'ecpub_trustchain_testnet.pem', 'triblerd.conf']
                for backup_file in backup_files:
                    dir_copy(src_state_dir / backup_file, dest_state_dir / backup_file)

    def notify_starting(self):
        """
        Broadcast a notification (event) that the upgrader is starting doing work
        after a check has established work on the db is required.
        Will only fire once.
        """
        if not self.notified:
            self.notified = True
            self.session.notifier.notify(NTFY.UPGRADER_STARTED)

    def notify_done(self):
        """
        Broadcast a notification (event) that the upgrader is done.
        """
        self.session.notifier.notify(NTFY.UPGRADER_DONE)
