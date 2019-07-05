from __future__ import absolute_import

import logging
import os
import shutil

from twisted.internet.defer import succeed

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Upgrade.config_converter import convert_config_to_tribler71
from Tribler.Core.Upgrade.db72_to_pony import DispersyToPonyMigration, cleanup_pony_experimental_db, should_upgrade
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.simpledefs import NTFY_FINISHED, NTFY_STARTED, NTFY_UPGRADER, NTFY_UPGRADER_TICK


def cleanup_noncompliant_channel_torrents(state_dir):
    channels_dir = os.path.join(state_dir, "channels")
    # Remove torrents contents
    if os.path.exists(channels_dir):
        for d in os.listdir(channels_dir):
            if len(os.path.splitext(d)[0]) != CHANNEL_DIR_NAME_LENGTH:
                dir_path = os.path.join(channels_dir, d)
                # We remove both malformed channel dirs and .torrent and .mdblob files for personal channel
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
                elif os.path.isfile(dir_path):
                    os.unlink(dir_path)

    # Remove .state torrent resume files
    resume_dir = os.path.join(state_dir, "dlcheckpoints")
    if os.path.exists(resume_dir):
        for f in os.listdir(resume_dir):
            file_path = os.path.join(resume_dir, f)
            pstate = CallbackConfigParser()
            pstate.read_file(file_path)

            if pstate and pstate.has_option('download_defaults', 'channel_download') and \
                    pstate.get('download_defaults', 'channel_download'):
                try:
                    name = pstate.get('state', 'metainfo')['info']['name']
                    if name and len(name) != CHANNEL_DIR_NAME_LENGTH:
                        os.unlink(file_path)
                except (TypeError, KeyError, ValueError):
                    pass


class TriblerUpgrader(object):

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

        self.notified = False
        self.is_done = False
        self.failed = True

        self.current_status = u"Initializing"
        self._dtp72 = None
        self.skip_upgrade_called = False

    def skip(self):
        self.skip_upgrade_called = True
        if self._dtp72:
            self._dtp72.shutting_down = True

    def run(self):
        """
        Run the upgrader if it is enabled in the config.

        Note that by default, upgrading is enabled in the config. It is then disabled
        after upgrading to Tribler 7.
        """

        return self.upgrade_72_to_pony()

    def update_status(self, status_text):
        self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, status_text)
        self.current_status = status_text

    def upgrade_72_to_pony(self):
        old_database_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'tribler.sdb')
        new_database_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'metadata.db')
        channels_dir = os.path.join(self.session.config.get_chant_channels_dir())

        if os.path.exists(new_database_path):
            cleanup_pony_experimental_db(new_database_path)
            cleanup_noncompliant_channel_torrents(self.session.config.get_state_dir())

        self._dtp72 = DispersyToPonyMigration(old_database_path, self.update_status, logger=self._logger)
        if not should_upgrade(old_database_path, new_database_path, logger=self._logger):
            self._dtp72 = None
            return succeed(None)
        # This thing is here mostly for the skip upgrade test to work...
        self._dtp72.shutting_down = self.skip_upgrade_called
        self.notify_starting()
        # We have to create the Metadata Store object because the LaunchManyCore has not been started yet
        mds = MetadataStore(new_database_path, channels_dir, self.session.trustchain_keypair, disable_sync=True)
        self._dtp72.initialize(mds)

        def finish_migration(_):
            mds.shutdown()
            self.notify_done()

        def log_error(failure):
            self._logger.error("Error in Upgrader callback chain: %s", failure)
        return self._dtp72.do_migration().addCallbacks(finish_migration, log_error)

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
