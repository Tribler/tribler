import logging
import os
import shutil
from configparser import MissingSectionHeaderError, ParsingError

from pony.orm import db_session, delete

from tribler_common.simpledefs import NTFY, STATEDIR_DB_DIR, STATEDIR_CHANNELS_DIR

from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.metadata_store.category_filter.l2_filter import is_forbidden
from tribler_core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT
from tribler_core.components.metadata_store.db.store import (
    MetadataStore,
    sql_create_partial_index_channelnode_metadata_type,
    sql_create_partial_index_channelnode_subscribed,
    sql_create_partial_index_torrentstate_last_check,
)
from tribler_core.components.upgrade.implementation.config_converter import convert_config_to_tribler74, \
    convert_config_to_tribler75, convert_config_to_tribler76
from tribler_core.components.upgrade.implementation.db8_to_db10 import PonyToPonyMigration, get_db_version
from tribler_core.components.upgrade.implementation.legacy_to_pony import DispersyToPonyMigration, \
    cleanup_pony_experimental_db, should_upgrade
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

        Note that by default, upgrading is enabled in the config. It is then disabled
        after upgrading to Tribler 7.
        """

        await self.upgrade_72_to_pony()
        self.upgrade_pony_db_6to7()
        self.upgrade_pony_db_7to8()
        await self.upgrade_pony_db_8to10()
        self.upgrade_pony_db_10to11()
        convert_config_to_tribler74(self.state_dir)
        convert_config_to_tribler75(self.state_dir)
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

    def upgrade_pony_db_7to8(self):
        """
        Upgrade GigaChannel DB from version 7 (7.4.x) to version 8 (7.5.x).
        Migration should be relatively fast, so we do it in the foreground.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, self.channels_dir, self.trustchain_keypair,
                            disable_sync=True, check_tables=False, db_version=7)
        self.do_upgrade_pony_db_7to8(mds)
        mds.shutdown()

    def do_upgrade_pony_db_7to8(self, mds):
        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != 7:
                return
            # Just in case, we skip index creation if it is somehow already there
            if not list(mds._db.execute('PRAGMA index_info("idx_channelnode__metadata_type")')):
                sql = 'CREATE INDEX "idx_channelnode__metadata_type" ON "ChannelNode" ("metadata_type")'
                mds._db.execute(sql)
            mds.Vsids[0].exp_period = 24.0 * 60 * 60 * 3
            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(8)
        return

    def upgrade_pony_db_6to7(self):
        """
        Upgrade GigaChannel DB from version 6 (7.3.0) to version 7 (7.3.1).
        Migration should be relatively fast, so we do it in the foreground, without notifying the user
        and breaking it in smaller chunks as we do with 72_to_pony.
        """
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, self.channels_dir, self.trustchain_keypair,
                            disable_sync=True, check_tables=False, db_version=6)
        self.do_upgrade_pony_db_6to7(mds)
        mds.shutdown()

    def do_upgrade_pony_db_6to7(self, mds):
        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != 6:
                return
            for c in mds.ChannelMetadata.select_by_sql(f"""
                select rowid, title, tags, metadata_type from ChannelNode
                where metadata_type = {CHANNEL_TORRENT}
            """):
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
        return

    def update_status(self, status_text):
        self.notifier.notify(NTFY.UPGRADER_TICK, status_text)

    async def upgrade_72_to_pony(self):
        old_database_path = self.state_dir / STATEDIR_DB_DIR / 'tribler.sdb'
        new_database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if new_database_path.exists():
            cleanup_pony_experimental_db(str(new_database_path))
            cleanup_noncompliant_channel_torrents(self.state_dir)

        self._dtp72 = DispersyToPonyMigration(old_database_path, self.update_status, logger=self._logger)
        if not should_upgrade(old_database_path, new_database_path, logger=self._logger):
            self._dtp72 = None
            return
        # This thing is here mostly for the skip upgrade test to work...
        self._dtp72.shutting_down = self.skip_upgrade_called
        self.notify_starting()
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        mds = MetadataStore(new_database_path, self.channels_dir, self.trustchain_keypair,
                            disable_sync=True, db_version=6)
        self._dtp72.initialize(mds)

        try:
            await self._dtp72.do_migration()
        except Exception as e:
            self._logger.error("Error in Upgrader callback chain: %s", e)
        finally:
            mds.shutdown()
            self.notify_done()

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
