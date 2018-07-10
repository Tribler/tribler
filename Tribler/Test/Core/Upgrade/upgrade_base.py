import os
import shutil

from configobj import ConfigObj
from twisted.internet.defer import inlineCallbacks

import Tribler
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Config.tribler_config import TriblerConfig, CONFIG_SPEC_PATH
from Tribler.Core.Session import Session
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class MockTorrentStore(object):
            pass


class AbstractUpgrader(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    DATABASES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"../data/upgrade_databases/"))

    def write_data_to_file(self, file_name):
        with open(file_name, 'w') as file:
            file.write("lorem ipsum")
            file.close()

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(AbstractUpgrader, self).setUp()
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH))
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_collecting_dir(os.path.join(self.session_base_dir, 'torrent_collecting_dir'))
        self.session = Session(self.config)
        self.sqlitedb = None
        self.torrent_store = None

    def tearDown(self):
        if self.torrent_store:
            self.torrent_store.close()

        super(AbstractUpgrader, self).tearDown()

        if self.sqlitedb:
            self.sqlitedb.close()
        self.sqlitedb = None
        self.session = None

    def copy_and_initialize_upgrade_database(self, db_name):

        # create a file to be removed in the thumbnails
        os.mkdir(self.session.config.get_torrent_collecting_dir())
        os.mkdir(os.path.join(self.session.config.get_torrent_collecting_dir(), 'dir1'))
        self.write_data_to_file(os.path.join(self.session.config.get_torrent_collecting_dir(), 'dir1', 'file1.txt'))

        os.mkdir(os.path.join(self.session_base_dir, 'sqlite'))
        shutil.copyfile(os.path.join(self.DATABASES_DIR, db_name),
                        os.path.join(self.session.config.get_state_dir(), 'sqlite', 'tribler.sdb'))
        shutil.copyfile(os.path.join(self.DATABASES_DIR, 'torrent_upgrade_64_dispersy.db'),
                        os.path.join(self.session.config.get_state_dir(), 'sqlite', 'dispersy.db'))
        db_path = os.path.join(self.session.config.get_state_dir(), 'sqlite', 'tribler.sdb')
        self.sqlitedb = SQLiteCacheDB(db_path)
        self.sqlitedb.initialize()
        self.sqlitedb.initial_begin()
        self.session.sqlite_db = self.sqlitedb
