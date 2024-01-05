import logging
import os
import shutil
import time
from configparser import MissingSectionHeaderError, ParsingError
from contextlib import suppress
from functools import wraps
from types import SimpleNamespace
from typing import List, Optional, Tuple

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session

from tribler.core.components.database.db.orm_bindings.torrent_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler.core.components.database.db.store import (
    CURRENT_DB_VERSION, MetadataStore,
    sql_create_partial_index_torrentstate_last_check,
)
from tribler.core.upgrade.config_converter import convert_config_to_tribler76
from tribler.core.upgrade.db8_to_db10 import PonyToPonyMigration
from tribler.core.upgrade.knowledge_to_triblerdb.migration import MigrationKnowledgeToTriblerDB
from tribler.core.upgrade.tags_to_knowledge.migration import MigrationTagsToKnowledge
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.tags_db import TagDatabase
from tribler.core.upgrade.tribler_db.migration_chain import TriblerDatabaseMigrationChain
from tribler.core.utilities.configparser import CallbackConfigParser
from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.pony_utils import get_db_version
from tribler.core.utilities.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_DB_DIR


# pylint: disable=protected-access

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


def catch_db_is_corrupted_exception(upgrader_method):
    # This decorator applied for TriblerUpgrader methods. It suppresses and remembers the DatabaseIsCorrupted exception.
    # As a result, if one upgrade method raises an exception, the following upgrade methods are still executed.
    #
    # The reason for this is the following: it is possible that one upgrade method upgrades database A
    # while the following upgrade method upgrades database B. If a corruption is detected in the database A,
    # the database B still needs to be upgraded. So, we want to temporarily suppress the DatabaseIsCorrupted exception
    # until all upgrades are executed.
    #
    # If an upgrade finds the database to be corrupted, the database is marked as corrupted. Then, the next upgrade
    # will rename the corrupted database file (the get_db_version call handles this) and immediately return because
    # there is no database to upgrade. So, if one upgrade function detects database corruption, all the following
    # upgrade functions for this specific database will skip the actual upgrade. As a result, a new database with
    # the current DB version will be created on the Tribler Core start.

    @wraps(upgrader_method)
    def new_method(*args, **kwargs):
        try:
            upgrader_method(*args, **kwargs)
        except DatabaseIsCorrupted as exc:
            self: TriblerUpgrader = args[0]
            self._logger.exception(exc)

            if not self._db_is_corrupted_exception:
                self._db_is_corrupted_exception = exc  # Suppress and remember the exception to re-raise it later

    return new_method


class TriblerUpgrader:

    def __init__(self, state_dir: Path, channels_dir: Path, primary_key: LibNaCLSK, secondary_key: Optional[LibNaCLSK],
                 interrupt_upgrade_event=None, update_status_callback=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir
        self.channels_dir = channels_dir
        self.primary_key = primary_key
        self.secondary_key = secondary_key
        self._update_status_callback = update_status_callback

        self.interrupt_upgrade_event = interrupt_upgrade_event or (lambda: False)

        self.failed = True
        self._pony2pony = None
        self._db_is_corrupted_exception: Optional[DatabaseIsCorrupted] = None

    @property
    def shutting_down(self):
        return self.interrupt_upgrade_event()

    def run(self):
        """
        Run the upgrader if it is enabled in the config.
        """
        self._logger.info('Run')

        self.upgrade_pony_db_8to10()
        self.upgrade_pony_db_10to11()
        convert_config_to_tribler76(self.state_dir)
        self.upgrade_pony_db_11to12()
        self.upgrade_pony_db_12to13()
        self.upgrade_pony_db_13to14()
        self.upgrade_tags_to_knowledge()
        self.remove_old_logs()
        self.upgrade_pony_db_14to15()
        self.upgrade_knowledge_to_tribler_db()
        self.remove_bandwidth_db()

        migration_chain = TriblerDatabaseMigrationChain(self.state_dir)
        migration_chain.execute()

        if self._db_is_corrupted_exception:
            # The current code is executed in the worker's thread. After all upgrade methods are executed,
            # we re-raise the delayed exception, and then it is received and handled in the main thread
            # by the UpgradeManager.on_worker_finished signal handler.
            raise self._db_is_corrupted_exception  # pylint: disable=raising-bad-type

    def remove_old_logs(self) -> Tuple[List[Path], List[Path]]:
        self._logger.info(f'Remove old logs')

        log_files = list(self.state_dir.glob('**/*.log'))
        log_files.extend(self.state_dir.glob('**/*.log.?'))

        removed_files = []
        left_files = []

        for log_file in log_files:
            self._logger.info(f'Remove: {log_file}')
            try:
                log_file.unlink(missing_ok=True)
            except OSError as e:
                self._logger.exception(e)
                left_files.append(log_file)
            else:
                removed_files.append(log_file)

        return removed_files, left_files

    @catch_db_is_corrupted_exception
    def upgrade_tags_to_knowledge(self):
        self._logger.info('Upgrade tags to knowledge')
        migration = MigrationTagsToKnowledge(self.state_dir, self.secondary_key)
        migration.run()

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_14to15(self):
        self._logger.info('Upgrade Pony DB from version 14 to version 15')
        mds_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not mds_path.exists() or get_db_version(mds_path, CURRENT_DB_VERSION) > 14:
            # No need to update if the database does not exist or is already updated
            return  # pragma: no cover

        mds = MetadataStore(mds_path, self.channels_dir, self.primary_key, disable_sync=True,
                            check_tables=False, db_version=14) if mds_path.exists() else None

        self.do_upgrade_pony_db_14to15(mds)
        if mds:
            mds.shutdown()

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_13to14(self):
        self._logger.info('Upgrade Pony DB from version 13 to version 14')
        mds_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        tagdb_path = self.state_dir / STATEDIR_DB_DIR / 'tags.db'

        if not mds_path.exists() or get_db_version(mds_path, CURRENT_DB_VERSION) > 13:
            # No need to update if the database does not exist or is already updated
            return  # pragma: no cover

        mds = MetadataStore(mds_path, self.channels_dir, self.primary_key, disable_sync=True,
                            check_tables=False, db_version=13) if mds_path.exists() else None
        tag_db = TagDatabase(str(tagdb_path), create_tables=False,
                             check_tables=False) if tagdb_path.exists() else None

        self.do_upgrade_pony_db_13to14(mds, tag_db)
        if mds:
            mds.shutdown()
        if tag_db:
            tag_db.shutdown()

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_12to13(self):
        """
        Upgrade GigaChannel DB from version 12 (7.9.x) to version 13 (7.11.x).
        Version 12 adds index for TorrentState.last_check attribute.
        """
        self._logger.info('Upgrade Pony DB 12 to 13')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists() or get_db_version(database_path, CURRENT_DB_VERSION) > 12:
            # No need to update if the database does not exist or is already updated
            return  # pragma: no cover

        mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                            disable_sync=True, check_tables=False, db_version=12)
        self.do_upgrade_pony_db_12to13(mds)
        mds.shutdown()

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_11to12(self):
        """
        Upgrade GigaChannel DB from version 11 (7.8.x) to version 12 (7.9.x).
        Version 12 adds a `json_text`, `binary_data` and `data_type` fields
        to TorrentState table if it already does not exist.
        """
        self._logger.info('Upgrade Pony DB 11 to 12')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists() or get_db_version(database_path, CURRENT_DB_VERSION) > 11:
            # No need to update if the database does not exist or is already updated
            return  # pragma: no cover

        mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                            disable_sync=True, check_tables=False, db_version=11)
        self.do_upgrade_pony_db_11to12(mds)
        mds.shutdown()

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_10to11(self):
        """
        Upgrade GigaChannel DB from version 10 (7.6.x) to version 11 (7.7.x).
        Version 11 adds a `self_checked` field to TorrentState table if it
        already does not exist.
        """
        self._logger.info('Upgrade Pony DB 10 to 11')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists() or get_db_version(database_path, CURRENT_DB_VERSION) > 10:
            # No need to update if the database does not exist or is already updated
            return  # pragma: no cover

        # code of the migration
        mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                            disable_sync=True, check_tables=False, db_version=10)
        self.do_upgrade_pony_db_10to11(mds)
        mds.shutdown()

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

        db = mds.db  # pylint: disable=protected-access

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return
            self._logger.info(f'{from_version}->{to_version}')
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

            db_version.value = str(to_version)

    def do_upgrade_pony_db_14to15(self, mds: Optional[MetadataStore]):
        if not mds:
            return

        version = SimpleNamespace(current='14', next='15')
        with db_session:
            db_version = mds.get_value(key='db_version')
            if db_version != version.current:
                return

            self._logger.info('Clean the incorrectly set self_checked flag for health info in the db')
            sql = 'UPDATE "TorrentState" SET "self_checked" = 0 WHERE "self_checked" != 0;'
            cursor = mds.db.execute(sql)
            self._logger.info(f'The self_checked flag was cleared in {cursor.rowcount} rows')

            self._logger.info('Reset the last_check future timestamps values to zero')
            now = int(time.time())  # pylint: disable=unused-variable
            sql = 'UPDATE "TorrentState" SET "seeders" = 0, "leechers" = 0, "has_data" = 0, "last_check" = 0 ' \
                  ' WHERE "last_check" > $now;'
            cursor = mds.db.execute(sql)
            self._logger.info(f'{cursor.rowcount} rows with future last_check timestamps were reset')

            mds.set_value(key='db_version', value=version.next)

    def do_upgrade_pony_db_13to14(self, mds: Optional[MetadataStore], tags: Optional[TagDatabase]):
        def add_column(db, table_name, column_name, column_type):
            if not self.column_exists_in_table(db, table_name, column_name):
                db.execute(f'ALTER TABLE "{table_name}" ADD "{column_name}" {column_type} DEFAULT 0')

        if not mds:
            return

        version = SimpleNamespace(current='13', next='14')
        with db_session:
            db_version = mds.get_value(key='db_version')
            if db_version != version.current:
                return

            self._logger.info(f'{version.current}->{version.next}')

            if tags is not None:
                add_column(db=tags.instance, table_name='TorrentTagOp', column_name='auto_generated',
                           column_type='BOOLEAN')
                tags.instance.commit()

            add_column(db=mds.db, table_name='ChannelNode', column_name='tag_processor_version', column_type='INT')
            mds.db.commit()
            mds.set_value(key='db_version', value=version.next)

    def do_upgrade_pony_db_11to12(self, mds):
        from_version = 11
        to_version = 12

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return
            self._logger.info(f'{from_version}->{to_version}')
            # Just in case, we skip altering table if the column is somehow already there
            table_name = "ChannelNode"
            new_columns = [("json_text", "TEXT1"),
                           ("binary_data", "BLOB1"),
                           ("data_type", "TEXT1")]

            for column_name, datatype in new_columns:
                # pylint: disable=protected-access
                if not self.column_exists_in_table(mds.db, table_name, column_name):
                    sql = f'ALTER TABLE {table_name} ADD {column_name} {datatype};'
                    mds.db.execute(sql)

            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(to_version)

    def do_upgrade_pony_db_10to11(self, mds):
        from_version = 10
        to_version = 11

        with db_session:
            db_version = mds.MiscData.get(name="db_version")
            if int(db_version.value) != from_version:
                return
            self._logger.info(f'{from_version}->{to_version}')

            # Just in case, we skip altering table if the column is somehow already there
            table_name = "TorrentState"
            column_name = "self_checked"

            # pylint: disable=protected-access
            if not self.column_exists_in_table(mds.db, table_name, column_name):
                sql = f'ALTER TABLE {table_name} ADD {column_name} BOOLEAN default 0;'
                mds.db.execute(sql)

            db_version = mds.MiscData.get(name="db_version")
            db_version.value = str(to_version)

    @catch_db_is_corrupted_exception
    def upgrade_pony_db_8to10(self):
        """
        Upgrade GigaChannel DB from version 8 (7.5.x) to version 10 (7.6.x).
        This will recreate the database anew, which can take quite some time.
        """
        self._logger.info('Upgrading GigaChannel DB from version 8 to 10')
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'

        if not database_path.exists() or get_db_version(database_path, CURRENT_DB_VERSION) >= 10:
            # Either no old db exists, or the old db version is up to date  - nothing to do
            return

        self._logger.info('8->10')
        # Otherwise, start upgrading
        self.update_status("STARTING")
        tmp_database_path = database_path.parent / 'metadata_upgraded.db'
        # Clean the previous temp database
        tmp_database_path.unlink(missing_ok=True)

        # Create the new database
        mds = MetadataStore(tmp_database_path, None, self.primary_key,
                            disable_sync=True, db_version=10)
        with db_session(ddl=True):
            mds.drop_indexes()
            mds.drop_fts_triggers()
        mds.shutdown()

        self._pony2pony = PonyToPonyMigration(database_path, tmp_database_path, self.update_status,
                                              logger=self._logger,
                                              shutdown_set_callback=self.interrupt_upgrade_event)

        duration_base = self._pony2pony.do_migration()
        self._pony2pony.recreate_indexes(mds, duration_base)

        # Remove the old DB
        database_path.unlink(missing_ok=True)
        if not self._pony2pony.shutting_down:
            # Move the upgraded db in its place
            tmp_database_path.rename(database_path)
        else:
            # The upgrade process was either skipped or interrupted. Delete the temp upgrade DB.
            tmp_database_path.unlink(missing_ok=True)

        self.update_status("FINISHED")

    def update_status(self, status_text):
        self._logger.info(status_text)
        if self._update_status_callback:
            self._update_status_callback(status_text)

    def upgrade_knowledge_to_tribler_db(self):
        self._logger.info('Upgrade knowledge to tribler.db')
        migration = MigrationKnowledgeToTriblerDB(self.state_dir)
        migration.run()

    def remove_bandwidth_db(self):
        self._logger.info('Removing bandwidth database')

        db_path = Path(self.state_dir / STATEDIR_DB_DIR)

        for file_path in db_path.glob('bandwidth*'):
            self._logger.info(f'Removing {file_path}')
            with suppress(OSError):
                file_path.unlink(missing_ok=True)
