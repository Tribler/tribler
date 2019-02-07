from __future__ import absolute_import

import logging
import os

import apsw

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Upgrade.config_converter import convert_config_to_tribler71
from Tribler.Core.Upgrade.db72_to_pony import DispersyToPonyMigration, CONVERSION_FROM_72, CONVERSION_FINISHED
from Tribler.Core.simpledefs import NTFY_FINISHED, NTFY_STARTED, NTFY_UPGRADER, NTFY_UPGRADER_TICK


class TriblerUpgrader(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        self.notified = False
        self.is_done = False
        self.failed = True

        self.current_status = u"Initializing"

    def run(self):
        """
        Run the upgrader if it is enabled in the config.

        Note that by default, upgrading is enabled in the config. It is then disabled
        after upgrading to Tribler 7.
        """
        self.notify_starting()

        self.upgrade_72_to_pony()
        # self.upgrade_config_to_71()
        self.notify_done()

    def update_status(self, status_text):
        self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, status_text)
        self.current_status = status_text

    def upgrade_72_to_pony(self):
        old_database_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'tribler.sdb')
        old_database_exists = os.path.exists(old_database_path)

        if not old_database_exists:
            # no old DB to upgrade
            return

        # Check the old DB version
        try:
            connection = apsw.Connection(old_database_path)
            cursor = connection.cursor()
            cursor.execute('SELECT value FROM MyInfo WHERE entry == "version"')
            version = int(cursor.fetchone()[0])
            if version != 29:
                return
        except:
            self._logger.error("Can't open the old tribler.sdb file")
            return

        new_database_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'metadata.db')
        new_database_exists = os.path.exists(new_database_path)
        state = None  # Previous conversion state
        if new_database_exists:
            # Check for the old experimental version database
            # ACHTUNG!!! NUCLEAR OPTION!!! DO NOT MESS WITH IT!!!
            delete_old_db = False
            try:
                connection = apsw.Connection(new_database_path)
                cursor = connection.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'MiscData'")
                result = cursor.fetchone()
                delete_old_db = not bool(result[0] if result else False)
            except:
                return
            finally:
                try:
                    connection.close()
                except:
                    pass
            if delete_old_db:
                # We're looking at the old experimental version database. Delete it.
                os.unlink(new_database_path)
                new_database_exists = False

        if new_database_exists:
            # Let's check if we converted all/some entries
            try:
                cursor.execute('SELECT value FROM MiscData WHERE name == "db_version"')
                version = int(cursor.fetchone()[0])
                if version != 0:
                    connection.close()
                    return
                cursor.execute('SELECT value FROM MiscData WHERE name == "%s"' % CONVERSION_FROM_72)
                result = cursor.fetchone()
                if result:
                    state = result[0]
                    if state == CONVERSION_FINISHED:
                        connection.close()
                        return
            except:
                self._logger.error("Can't open the new metadata.db file")
                return
            finally:
                connection.close()

        channels_dir = os.path.join(self.session.config.get_chant_channels_dir())
        # We have to create the Metadata Store object because the LaunchManyCore has not been started yet
        mds = MetadataStore(new_database_path, channels_dir, self.session.trustchain_keypair)
        d = DispersyToPonyMigration(old_database_path, mds, self.update_status)

        d.initialize()

        d.convert_discovered_torrents()

        d.convert_discovered_channels()

        d.convert_personal_channel()

        d.update_trackers_info()

        d.mark_conversion_finished()
        # Notify GigaChannel Manager?

        mds.shutdown()

    def upgrade_config_to_71(self):
        """
        This method performs actions necessary to upgrade the configuration files to Tribler 7.1.
        """
        self.session.config = convert_config_to_tribler71(self.session.config)
        self.session.config.write()

    def notify_starting(self):
        """
        Broadcast a notification (event) that the upgrader is starting doing work
        after a check has established work on the db is required.
        Will only fire once.
        """
        if not self.notified:
            self.notified = True
            self.session.notifier.notify(NTFY_UPGRADER, NTFY_STARTED, None)

    def notify_done(self):
        """
        Broadcast a notification (event) that the upgrader is done.
        """
        self.session.notifier.notify(NTFY_UPGRADER, NTFY_FINISHED, None)
