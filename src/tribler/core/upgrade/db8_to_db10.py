import contextlib
import datetime
import logging
from collections import deque
from time import time as now

from pony.orm import db_session

from tribler.core.components.database.db.store import MetadataStore
from tribler.core.utilities.db_corruption_handling import sqlite_replacement

TABLE_NAMES = (
    "ChannelNode", "TorrentState", "TorrentState_TrackerState", "ChannelPeer", "ChannelVote", "TrackerState", "Vsids")


class PonyToPonyMigration:

    def __init__(self, old_db_path, new_db_path, notification_callback=None, logger=None, shutdown_set_callback=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.notification_callback = notification_callback
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.shutting_down = False
        self.shutdown_set_callback = shutdown_set_callback

    def must_shutdown(self):
        if self.shutdown_set_callback is not None:
            self.shutting_down = self.shutting_down or self.shutdown_set_callback()
        return self.shutting_down

    def update_status(self, status_text):
        if self.notification_callback:
            self.notification_callback(status_text)

    def update_convert_progress(self, amount, total, eta, message=""):
        self.update_status(
            f"{message}\n"
            f"Converted: {amount}/{total} ({(amount * 100) // total}%).\n"
            f"Time remaining: {eta}"
        )

    def convert(self, table_name, cursor, convert_command, total_to_convert, offset=0, message=""):
        """
        This method copies entries from one Pony db into another one splitting the process into chunks dynamically.
        Chunks splitting uses congestion-control-like algorithm. Awaits are necessary so the
        reactor can get an opportunity at serving other tasks, such as sending progress notifications to
        the GUI through the REST API.
        """
        last_commit_time = now()
        batch_size = 1000

        speed_list = deque(maxlen=20)

        reference_timedelta = 0.8
        while offset < total_to_convert:
            if self.must_shutdown():
                break
            end = offset + batch_size

            batch_start_time = now()
            convert_command(offset, batch_size)
            batch_end_time = now()
            batch_duration = batch_end_time - batch_start_time

            remaining = total_to_convert - offset
            est_speed = batch_size / max(batch_duration, 0.001)
            speed_list.append(est_speed)
            avg_est_speed = sum(speed_list) / len(speed_list)
            eta = str(datetime.timedelta(seconds=int(remaining / avg_est_speed)))

            self.update_convert_progress(offset, total_to_convert, eta, message)

            if batch_duration < reference_timedelta:
                new_batch_size = round(batch_size * 1.5)
            else:
                new_batch_size = round(batch_size * 0.9)

            # we want to guarantee that at least some entries will go through
            new_batch_size = max(50, new_batch_size)

            offset = end
            self._logger.info("Convert %s: %i/%i (%.2f%%), batch size %d batch duration %f new batch size %d",
                              table_name,
                              end,
                              total_to_convert,
                              end * 100.0 / total_to_convert,
                              batch_size,
                              batch_duration,
                              new_batch_size)

            batch_size = new_batch_size

            if offset >= total_to_convert or now() - last_commit_time > 10:
                self._logger.info("Upgrade: commit data")
                cursor.execute("commit")
                cursor.execute("begin transaction")
                last_commit_time = now()

    def get_table_entries_count(self, cursor, table_name):
        return cursor.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]

    def convert_table(self, cursor, table_name, column_names):
        column_names_joined = ", ".join(column_names)
        if "rowid" in column_names:
            order_column = "rowid"
        else:
            order_column = column_names[0]
        sql_command = f"INSERT OR IGNORE INTO {table_name} ({column_names_joined}) " + \
                      f"SELECT {column_names_joined} FROM old_db.{table_name} " + \
                      f"ORDER BY {order_column} " + \
                      f"LIMIT ? OFFSET ?;"

        def convert_command(offset, batch_size):
            try:
                cursor.execute(sql_command, (batch_size, offset))
            except Exception as e:
                self._logger.error("Upgrade: error while executing conversion command: %s:%s, SQL %s ",
                                   type(e).__name__, str(e), sql_command)
                # Bail out and stop the upgrade process
                self.shutting_down = True

        old_entries_count = self.get_table_entries_count(cursor, f"old_db.{table_name}")
        self.convert(table_name, cursor, convert_command, old_entries_count,
                     message=f"Converting DB table {table_name}")

    def do_migration(self):
        result = None  # estimated duration in seconds of ChannelNode table copying time
        try:
            old_table_columns = {}
            for table_name in TABLE_NAMES:
                old_table_columns[table_name] = get_table_columns(self.old_db_path, table_name)

            with contextlib.closing(sqlite_replacement.connect(self.new_db_path)) as connection:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute("PRAGMA journal_mode = OFF;")
                    cursor.execute("PRAGMA synchronous = OFF;")
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                    cursor.execute("PRAGMA temp_store = MEMORY;")
                    cursor.execute("PRAGMA cache_size = -204800;")
                    cursor.execute(f'ATTACH DATABASE "{self.old_db_path}" as old_db;')

                    for table_name in TABLE_NAMES:
                        t1 = now()
                        cursor.execute("BEGIN TRANSACTION;")
                        if not self.must_shutdown():
                            self.convert_table(cursor, table_name, old_table_columns[table_name])
                        cursor.execute("COMMIT;")
                        duration = now() - t1
                        self._logger.info(f"Upgrade: copied table {table_name} in {duration:.2f} seconds")

                        if table_name == 'ChannelNode':
                            result = duration

            self.update_status("Synchronizing the upgraded DB to disk, please wait.")
        except Exception as e:
            self._logger.error(f"Error during database upgrade: {type(e).__name__}:{str(e)}")
            self.shutting_down = True
        return result

    def recreate_indexes(self, mds: MetadataStore, base_duration):
        try:
            if not self.must_shutdown():
                self.do_recreate_indexes(mds, base_duration)
        except Exception as e:  # pylint: disable=broad-except  # pragma: no cover
            self._logger.error(f"Error during index re-building: {type(e).__name__}:{str(e)}")
            self.shutting_down = True

    def do_recreate_indexes(self, mds: MetadataStore, base_duration):
        index_total = None
        index_num = 0
        t0 = t1 = now()

        # SQLite callback handler to update progress bar during index creation
        def index_callback_handler():
            try:
                t2 = now()
                index_percentage = calc_progress(t2 - t1, base_duration / 8.0)
                total_percentage = (index_num * 100.0 + index_percentage) / index_total
                self.notification_callback(f"recreating indexes\n"
                                           f"{total_percentage:.2f}% done")
            except Exception as e:
                self._logger.error(f"Error in SQLite callback handler: {type(e).__name__}:{str(e)}")
                self.shutting_down = True

        # Recreate table indexes
        with db_session(ddl=True):
            connection = mds.db.get_connection()
            try:
                db_objects = mds.get_objects_to_create()
                index_total = len(db_objects)
                for i, obj in enumerate(db_objects):
                    index_num = i
                    t1 = now()
                    connection.set_progress_handler(index_callback_handler, 5000)
                    obj.create(mds.db.schema.provider, connection)
                    duration = now() - t1
                    self._logger.info(f"Upgrade: created {obj.name} in {duration:.2f} seconds")
            finally:
                connection.set_progress_handler(None, 0)

        duration = now() - t0
        self._logger.info(f'Recreated all indexes in {duration:.2f} seconds')
        t1 = now()

        # SQLite callback handler to update progress bar during FTS index creation
        def fts_callback_handler():
            try:
                t2 = now()
                self.notification_callback("adding full text search index...\n"
                                           f"{calc_progress(t2 - t1, base_duration):.2f}% done")
            except Exception as e:
                self._logger.error(f"Error in SQLite callback handler: {type(e).__name__}:{str(e)}")
                self.shutting_down = True

        # Create FTS index
        with db_session(ddl=True):
            mds.create_fts_triggers()
            connection = mds.db.get_connection()
            connection.set_progress_handler(fts_callback_handler, 5000)
            try:
                t = now()
                mds.fill_fts_index()
                duration = now() - t
                self._logger.info(f'Upgrade: fill FTS in {duration:.2f} seconds')
            finally:
                connection.set_progress_handler(None, 0)
        mds.shutdown()


def calc_progress(duration_now, duration_half=60.0):
    result = 100 * (1 - 1 / (1 + duration_now / (duration_half + 1)) ** 2)
    return result


def get_table_columns(db_path, table_name):
    with contextlib.closing(sqlite_replacement.connect(db_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute(f'SELECT * FROM {table_name} LIMIT 1')
        names = [description[0] for description in cursor.description]
    return names
