import logging
import os
import shutil
import time
from configparser import MissingSectionHeaderError, ParsingError
from types import SimpleNamespace
from typing import List, Optional, Tuple

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from pony.orm import db_session, delete

from tribler.core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler.core.components.metadata_store.db.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from tribler.core.components.metadata_store.db.store import (
    MetadataStore,
    sql_create_partial_index_channelnode_metadata_type,
    sql_create_partial_index_channelnode_subscribed,
    sql_create_partial_index_torrentstate_last_check,
)
from tribler.core.upgrade.config_converter import convert_config_to_tribler76
from tribler.core.upgrade.db8_to_db10 import PonyToPonyMigration, get_db_version
from tribler.core.upgrade.knowledge_to_triblerdb.migration import MigrationKnowledgeToTriblerDB
from tribler.core.upgrade.tags_to_knowledge.migration import MigrationTagsToKnowledge
from tribler.core.upgrade.tags_to_knowledge.previous_dbs.tags_db import TagDatabase
from tribler.core.upgrade.tribler_db.migration_chain import TriblerDatabaseMigrationChain
from tribler.core.utilities.configparser import CallbackConfigParser
from tribler.core.utilities.path_util import Path
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
        self.upgrade_bw_accounting_db_8to9()
        self.upgrade_pony_db_11to12()
        self.upgrade_pony_db_12to13()
        self.upgrade_pony_db_13to14()
        self.upgrade_tags_to_knowledge()
        self.remove_old_logs()
        self.upgrade_pony_db_14to15()
        self.upgrade_knowledge_to_tribler_db()

        migration_chain = TriblerDatabaseMigrationChain(self.state_dir)
        migration_chain.execute()

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

    def upgrade_tags_to_knowledge(self):
        self._logger.info('Upgrade tags to knowledge')
        migration = MigrationTagsToKnowledge(self.state_dir, self.secondary_key)
        migration.run()

    def upgrade_pony_db_14to15(self):
        self._logger.info('Upgrade Pony DB from version 14 to version 15')
        mds_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'

        mds = MetadataStore(mds_path, self.channels_dir, self.primary_key, disable_sync=True,
                            check_tables=False, db_version=14) if mds_path.exists() else None

        self.do_upgrade_pony_db_14to15(mds)
        if mds:
            mds.shutdown()

    def upgrade_pony_db_13to14(self):
        self._logger.info('Upgrade Pony DB from version 13 to version 14')
        mds_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        tagdb_path = self.state_dir / STATEDIR_DB_DIR / 'tags.db'

        mds = MetadataStore(mds_path, self.channels_dir, self.primary_key, disable_sync=True,
                            check_tables=False, db_version=13) if mds_path.exists() else None
        tag_db = TagDatabase(str(tagdb_path), create_tables=False,
                             check_tables=False) if tagdb_path.exists() else None

        self.do_upgrade_pony_db_13to14(mds, tag_db)
        if mds:
            mds.shutdown()
        if tag_db:
            tag_db.shutdown()

    def upgrade_pony_db_12to13(self):
        """
        Upgrade GigaChannel DB from version 12 (7.9.x) to version 13 (7.11.x).
        Version 12 adds index for TorrentState.last_check attribute.
        """
        self._logger.info('Upgrade Pony DB 12 to 13')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if database_path.exists():
            mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                                disable_sync=True, check_tables=False, db_version=12)
            self.do_upgrade_pony_db_12to13(mds)
            mds.shutdown()

    def upgrade_pony_db_11to12(self):
        """
        Upgrade GigaChannel DB from version 11 (7.8.x) to version 12 (7.9.x).
        Version 12 adds a `json_text`, `binary_data` and `data_type` fields
        to TorrentState table if it already does not exist.
        """
        self._logger.info('Upgrade Pony DB 11 to 12')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                            disable_sync=True, check_tables=False, db_version=11)
        self.do_upgrade_pony_db_11to12(mds)
        mds.shutdown()

    def upgrade_pony_db_10to11(self):
        """
        Upgrade GigaChannel DB from version 10 (7.6.x) to version 11 (7.7.x).
        Version 11 adds a `self_checked` field to TorrentState table if it
        already does not exist.
        """
        self._logger.info('Upgrade Pony DB 10 to 11')
        # We have to create the Metadata Store object because Session-managed Store has not been started yet
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists():
            return
        # code of the migration
        mds = MetadataStore(database_path, self.channels_dir, self.primary_key,
                            disable_sync=True, check_tables=False, db_version=10)
        self.do_upgrade_pony_db_10to11(mds)
        mds.shutdown()

    def upgrade_bw_accounting_db_8to9(self):
        """
        Upgrade the database with bandwidth accounting information from 8 to 9.
        Specifically, this upgrade wipes all transactions and addresses an issue where payouts with the wrong amount
        were made. Also see https://github.com/Tribler/tribler/issues/5789.
        """
        self._logger.info('Upgrade bandwidth accounting DB 8 to 9')
        to_version = 9

        database_path = self.state_dir / STATEDIR_DB_DIR / 'bandwidth.db'
        if not database_path.exists() or get_db_version(database_path) >= 9:
            return  # No need to update if the database does not exist or is already updated
        self._logger.info('bw8->9')
        db = BandwidthDatabase(database_path, self.primary_key.key.pk)

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

            db.execute(sql_create_partial_index_channelnode_metadata_type)
            db.execute(sql_create_partial_index_channelnode_subscribed)

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

    def upgrade_pony_db_8to10(self):
        """
        Upgrade GigaChannel DB from version 8 (7.5.x) to version 10 (7.6.x).
        This will recreate the database anew, which can take quite some time.
        """
        self._logger.info('Upgrading GigaChannel DB from version 8 to 10')
        database_path = self.state_dir / STATEDIR_DB_DIR / 'metadata.db'
        if not database_path.exists() or get_db_version(database_path) >= 10:
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
