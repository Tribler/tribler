import logging
import os
import shutil
from configparser import MissingSectionHeaderError, ParsingError

from pony.orm import db_session, delete

from tribler_common.simpledefs import NTFY, STATEDIR_CHANNELS_DIR, STATEDIR_DB_DIR

from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.components.metadata_store.db.store import (
    MetadataStore,
    sql_create_partial_index_channelnode_metadata_type,
    sql_create_partial_index_channelnode_subscribed,
    sql_create_partial_index_torrentstate_last_check,
)
from tribler_core.components.upgrade.implementation.config_converter import convert_config_to_tribler76
from tribler_core.components.upgrade.implementation.db8_to_db10 import PonyToPonyMigration, get_db_version
from tribler_core.notifier import Notifier
from tribler_core.utilities.configparser import CallbackConfigParser


def cleanup_noncompliant_channel_torrents(state_dir):
    logger = logging.getLogger(__name__)
    channels_dir = state_dir / STATEDIR_CHANNELS_DIR
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


class TriblerUpgrader:

    def __init__(self, state_dir, channels_dir, trustchain_keypair, notifier: Notifier):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir
        self.notifier = notifier
        self.channels_dir = channels_dir
        self.trustchain_keypair = trustchain_keypair

        self.notified = False
        self.failed = True

        self._dtp72 = None
        self._pony2pony = None
        self.skip_upgrade_called = False

    def skip(self):
        self.skip_upgrade_called = True
        if self._dtp72:
            self._dtp72.shutting_down = True
        if self._pony2pony:
            self._pony2pony.shutting_down = True

    async def run(self):
        """
        Run the upgrader if it is enabled in the config.
        """
        await self.upgrade_pony_db_8to10()
        self.upgrade_pony_db_10to11()
        convert_config_to_tribler76(self.state_dir)
        self.upgrade_bw_accounting_db_8to9()
        self.upgrade_pony_db_11to12()
        self.upgrade_pony_db_12to13()

    def upgrade_pony_db_12to13(self):
        """
        Upgrade GigaChannel DB from version 12 (7.9.x) to version 13 (7.11.x).
        Version 12 adds index for TorrentState.last_check attribute.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if database_path.exists():
            mds = MetadataStore(database_path, self.channels_dir, self.trustchain_keypair,
                                disable_sync=True, check_tables=False, db_version=12)
            self.do_upgrade_pony_db_12to13(mds)
            mds.shutdown()

    def upgrade_pony_db_11to12(self):
        """
        Upgrade GigaChannel DB from version 11 (7.8.x) to version 12 (7.9.x).
        Version 12 adds a `json_text`, `binary_data` and `data_type` fields
        to TorrentState table if it already does not exist.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, self.channels_dir, self.trustchain_keypair,
                            disable_sync=True, check_tables=False, db_version=11)
        self.do_upgrade_pony_db_11to12(mds)
        mds.shutdown()

    def upgrade_pony_db_10to11(self):
        """
        Upgrade GigaChannel DB from version 10 (7.6.x) to version 11 (7.7.x).
        Version 11 adds a `self_checked` field to TorrentState table if it
        already does not exist.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, self.channels_dir, self.trustchain_keypair,
                            disable_sync=True, check_tables=False, db_version=10)
        self.do_upgrade_pony_db_10to11(mds)
        mds.shutdown()

    def upgrade_bw_accounting_db_8to9(self):
        """
        Upgrade the database with bandwidth accounting information from 8 to 9.
        Specifically, this upgrade wipes all transactions and addresses an issue where payouts with the wrong amount
        were made. Also see https://github.com/Tribler/tribler/issues/5789.
        """
        to_version = 9

        database_path = self.state_dir / STATEDIR_DB_DIR / 'bandwidth.db'
        if not database_path.exists() or get_db_version(database_path) >= 9:
            return  # No need to update if the database does not exist or is already updated
        db = BandwidthDatabase(database_path, self.trustchain_keypair.key.pk)

        # Wipe all transactions and bandwidth history
        with db_session:
            delete(tx for tx in db.BandwidthTransaction)
            delete(item for item in db.BandwidthHistory)

            # Update db version
            db_version = db.MiscData.get(name="db_version")
            db_version.value = str(to_version)

        db.shutdown()

    def column_exists_in_table(self, db, table, column):
        pragma = f'SELECT COUNT(*) FROM pragma_table_info("{table}") WHERE name="{column}"'
        result = list(db.execute(pragma))
        # If the column exists, result = [(1, )] else [(0, )]
        return result[0][0] == 1

    def trigger_exists(self, db, trigger_name):
        sql = f"select 1 from sqlite_master where type = 'trigger' and name = '{trigger_name}'"
        result = db.execute(sql).fetchone()
        return result is not None

    def do_upgrade_pony_db_12to13(self, mds):
        from_version = 12
        to_version = 13

        db = mds._db  # pylint: disable=protected-access

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return

            db.execute('DROP INDEX IF EXISTS idx_channelnode__public_key')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__status')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__size')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__share')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__subscribed')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__votes')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__tags')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__title')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__num_entries')
            db.execute('DROP INDEX IF EXISTS idx_channelnode__metadata_type')

            if not self.column_exists_in_table(db, 'TorrentState', 'has_data'):
                db.execute('ALTER TABLE "TorrentState" ADD "has_data" BOOLEAN DEFAULT 0')
                db.execute('UPDATE "TorrentState" SET "has_data" = 1 WHERE last_check > 0')
            db.execute(sql_create_partial_index_torrentstate_last_check)
            mds.create_torrentstate_triggers()

            db.execute(sql_create_partial_index_channelnode_metadata_type)
            db.execute(sql_create_partial_index_channelnode_subscribed)

            db_version.value = str(to_version)

    def do_upgrade_pony_db_11to12(self, mds):
        from_version = 11
        to_version = 12

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return

            # Just in case, we skip altering table if the column is somehow already there
            table_name = "ChannelNode"
            new_columns = [("json_text", "TEXT1"),
                           ("binary_data", "BLOB1"),
                           ("data_type", "TEXT1")]

            for column_name, datatype in new_columns:
                # pylint: disable=protected-access
                if not self.column_exists_in_table(mds._db, table_name, column_name):
                    sql = f'ALTER TABLE {table_name} ADD {column_name} {datatype};'
                    mds._db.execute(sql)

            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(to_version)

    def do_upgrade_pony_db_10to11(self, mds):
        from_version = 10
        to_version = 11

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return

            # Just in case, we skip altering table if the column is somehow already there
            table_name = "TorrentState"
            column_name = "self_checked"

            # pylint: disable=protected-access
            if not self.column_exists_in_table(mds._db, table_name, column_name):
                sql = f'ALTER TABLE {table_name} ADD {column_name} BOOLEAN default 0;'
                mds._db.execute(sql)

            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(to_version)

    async def upgrade_pony_db_8to10(self):
        """
        Upgrade GigaChannel DB from version 8 (7.5.x) to version 10 (7.6.x).
        This will recreate the database anew, which can take quite some time.
        The code is based on the copy-pasted upgrade_72_to_pony routine which is asynchronous and
        reports progress to the user.
        """
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists() or get_db_version(database_path) >= 10:
            # Either no old db exists, or the old db version is up to date  - nothing to do
            return

        # Otherwise, start upgrading
        self.notify_starting()
        tmp_database_path = database_path.parent / 'metadata_upgraded.db'
        # Clean the previous temp database
        if tmp_database_path.exists():
            tmp_database_path.unlink()

        # Create the new database
        mds = MetadataStore(tmp_database_path, None, self.trustchain_keypair,
                            disable_sync=True, db_version=10)
        with db_session(ddl=True):
            mds.drop_indexes()
            mds.drop_fts_triggers()
        mds.shutdown()

        self._pony2pony = PonyToPonyMigration(database_path, tmp_database_path, self.update_status, logger=self._logger)

        duration_base = await self._pony2pony.do_migration()
        await self._pony2pony.recreate_indexes(mds, duration_base)

        # Remove the old DB
        database_path.unlink()
        if not self._pony2pony.shutting_down:
            # Move the upgraded db in its place
            tmp_database_path.rename(database_path)
        else:
            # The upgrade process was either skipped or interrupted. Delete the temp upgrade DB.
            if tmp_database_path.exists():
                tmp_database_path.unlink()

        self.notify_done()

    def update_status(self, status_text):
        self.notifier.notify(NTFY.UPGRADER_TICK, status_text)

    def notify_starting(self):
        """
        Broadcast a notification (event) that the upgrader is starting doing work
        after a check has established work on the db is required.
        Will only fire once.
        """
        if not self.notified:
            self.notified = True
            self.notifier.notify(NTFY.UPGRADER_STARTED)

    def notify_done(self):
        """
        Broadcast a notification (event) that the upgrader is done.
        """
        self.notifier.notify(NTFY.UPGRADER_DONE)
