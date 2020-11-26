import contextlib
import datetime
import logging
import sqlite3
from asyncio import sleep

TABLE_NAMES = (
    "ChannelNode", "TorrentState", "TorrentState_TrackerState", "ChannelPeer", "ChannelVote", "TrackerState", "Vsids")


class PonyToPonyMigration(object):

    def __init__(self, old_db_path, new_db_path, notifier_callback=None, logger=None):
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self.notifier_callback = notifier_callback
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.shutting_down = False

    async def update_convert_progress(self, amount, total, elapsed, message=""):
        if self.notifier_callback:
            elapsed = 0.0001 if elapsed == 0.0 else elapsed
            amount = amount or 1
            est_speed = amount / elapsed
            eta = str(datetime.timedelta(seconds=int((total - amount) / est_speed)))
            self.notifier_callback(
                f"{message}\nConverted: {amount}/{total} ({(amount * 100) // total}%).\nTime remaining: {eta}"
            )
            await sleep(0.001)

    async def convert_async(self, convert_command, total_to_convert, offset=0, message=""):
        """
        This method copies entries from one Pony db into another one splitting the process into chunks dynamically.
        Chunks splitting uses congestion-control-like algorithm. Awaits are necessary so the
        reactor can get an opportunity at serving other tasks, such as sending progress notifications to
        the GUI through the REST API.
        """
        start_time = datetime.datetime.utcnow()
        batch_size = 100

        reference_timedelta = datetime.timedelta(milliseconds=1000)
        while offset < total_to_convert:
            if self.shutting_down:
                break
            end = offset + batch_size

            batch_start_time = datetime.datetime.now()
            convert_command(offset, batch_size)
            batch_end_time = datetime.datetime.now() - batch_start_time

            elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
            await self.update_convert_progress(offset, total_to_convert, elapsed, message)
            target_coeff = (batch_end_time.total_seconds() / reference_timedelta.total_seconds())
            if target_coeff < 0.8:
                batch_size += batch_size
            elif target_coeff > 1.1:
                batch_size = int(float(batch_size) / target_coeff)
            # we want to guarantee that at least some entries will go through
            batch_size = batch_size if batch_size > 10 else 10
            self._logger.info("Converted: %i/%i %f ",
                              offset + batch_size, total_to_convert, float(batch_end_time.total_seconds()))
            offset = end

    def get_table_entries_count(self, cursor, table_name):
        return cursor.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]

    async def convert_table(self, cursor, table_name, column_names):
        def convert_command(offset, batch_size):
            sql_command = None
            try:
                column_names_joined = ", ".join(column_names)
                if "rowid" in column_names:
                    order_column = "rowid"
                else:
                    order_column = column_names[0]
                sql_command = f"INSERT OR IGNORE INTO {table_name} ({column_names_joined}) " + \
                              f"SELECT {column_names_joined} FROM old_db.{table_name} " + \
                              f"ORDER BY {order_column} " + \
                              f"LIMIT {batch_size} {('OFFSET ' + str(offset)) if offset else ''} ;"
                cursor.execute(sql_command)
            except Exception as e:
                # Bail out and stop the upgrade process
                self.shutting_down = True
                self._logger.error("Error while executing conversion command: %s, SQL %s ", str(e), sql_command)

        old_entries_count = self.get_table_entries_count(cursor, f"old_db.{table_name}")
        await self.convert_async(convert_command, old_entries_count, message=f"Converting DB table {table_name}")

    async def do_migration(self):

        old_table_columns = {}
        for table_name in TABLE_NAMES:
            old_table_columns[table_name] = get_table_columns(self.old_db_path, table_name)

        with contextlib.closing(sqlite3.connect(self.new_db_path)) as connection, connection:
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode = OFF;")
            cursor.execute("PRAGMA synchronous = OFF;")
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("PRAGMA temp_store = MEMORY;")
            cursor.execute(f'ATTACH DATABASE "{self.old_db_path}" as old_db;')

            for table_name in TABLE_NAMES:
                cursor.execute("BEGIN TRANSACTION;")
                if not self.shutting_down:
                    await self.convert_table(cursor, table_name, old_table_columns[table_name])
                cursor.execute("COMMIT;")
        self.notifier_callback("Synchronizing the upgraded DB to disk, please wait.")


def get_table_columns(db_path, table_name):
    with contextlib.closing(sqlite3.connect(db_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute(f'SELECT * FROM {table_name} LIMIT 1')
        names = [description[0] for description in cursor.description]
    return names


def get_db_version(db_path):
    with contextlib.closing(sqlite3.connect(db_path)) as connection, connection:
        cursor = connection.cursor()
        cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
        version = int(cursor.fetchone()[0])
    return version
