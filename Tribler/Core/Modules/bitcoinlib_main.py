"""
This file contains the 'patched' main method for bitcoinlib.
The original main file has many side effects and creates all kinds of directories across the system.
This file makes sure that all these directories are created inside a designated (wallet) directory.
It should be imported before any bitcoinlib imports.
"""
import imp
import os
import sys

# Important import, do not remove! Files importing stuff from this file, rely on availability of the logger module.
import logging

sys.modules["bitcoinlib.main"] = sys.modules[__name__]


DEFAULT_DOCDIR = None
DEFAULT_DATABASEDIR = None
DEFAULT_LOGDIR = None
DEFAULT_SETTINGSDIR = None
CURRENT_INSTALLDIR = None
CURRENT_INSTALLDIR_DATA = None
DEFAULT_DATABASEFILE = 'bitcoinlib.sqlite'
DEFAULT_DATABASE = None
TIMEOUT_REQUESTS = 5


def initialize_lib(wallet_dir):
    global DEFAULT_DOCDIR, DEFAULT_DATABASEDIR, DEFAULT_LOGDIR, DEFAULT_SETTINGSDIR, DEFAULT_DATABASE,\
        CURRENT_INSTALLDIR, CURRENT_INSTALLDIR_DATA
    try:
        bitcoinlib_path = imp.find_module('bitcoinlib')[1]
        CURRENT_INSTALLDIR = bitcoinlib_path
        CURRENT_INSTALLDIR_DATA = os.path.join(bitcoinlib_path, 'data')
        DEFAULT_DOCDIR = wallet_dir
        DEFAULT_DATABASEDIR = os.path.join(DEFAULT_DOCDIR, 'database/')
        DEFAULT_LOGDIR = os.path.join(DEFAULT_DOCDIR, 'log/')
        DEFAULT_SETTINGSDIR = os.path.join(DEFAULT_DOCDIR, 'config/')
        DEFAULT_DATABASE = DEFAULT_DATABASEDIR + DEFAULT_DATABASEFILE

        if not os.path.exists(DEFAULT_DOCDIR):
            os.makedirs(DEFAULT_DOCDIR)
        if not os.path.exists(DEFAULT_LOGDIR):
            os.makedirs(DEFAULT_LOGDIR)
        if not os.path.exists(DEFAULT_SETTINGSDIR):
            os.makedirs(DEFAULT_SETTINGSDIR)

        # Copy data and settings file
        from shutil import copyfile

        src_files = os.listdir(CURRENT_INSTALLDIR_DATA)
        for file_name in src_files:
            full_file_name = os.path.join(CURRENT_INSTALLDIR_DATA, file_name)
            if os.path.isfile(full_file_name):
                copyfile(full_file_name, os.path.join(DEFAULT_SETTINGSDIR, file_name))

        # Clear everything related to bitcoinlib from sys.modules
        for module_name in sys.modules.keys():
            if module_name.startswith('bitcoinlib') and module_name != 'bitcoinlib.main':
                del sys.modules[module_name]
    except ImportError:
        pass
