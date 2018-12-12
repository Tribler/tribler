"""
This file contains the 'patched' main method for bitcoinlib.
The original main file has many side effects and creates all kinds of directories across the system.
This file makes sure that all these directories are created inside a designated (wallet) directory.
It should be imported before any bitcoinlib imports.
"""
from __future__ import absolute_import

import ast
import imp
import os
import sys

# Important import, do not remove! Files importing stuff from this file, rely on availability of the logger module.
import logging
from logging.handlers import RotatingFileHandler

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

        # Extract all variable assignments from the original file and make sure these variables are initialized.
        excluded_assignments = ['logfile', 'handler', 'logger', 'formatter']
        with open(os.path.join(CURRENT_INSTALLDIR, 'main.py'), 'rb') as source_file:
            file_contents = source_file.read()
            ast_module_node = ast.parse(file_contents)
            for node in ast.iter_child_nodes(ast_module_node):
                if isinstance(node, ast.Assign):
                    node_id, value = node.targets[0].id, node.value
                    if not hasattr(sys.modules[__name__], node_id) and node_id not in excluded_assignments:
                        output = eval(compile(ast.Expression(value), '<string>', 'eval'))
                        setattr(sys.modules[__name__], node_id, output)

        # Clear everything related to bitcoinlib from sys.modules
        for module_name in list(sys.modules):
            if module_name.startswith('bitcoinlib') and module_name != 'bitcoinlib.main':
                del sys.modules[module_name]

        # Make sure the OPCODES are known to the transaction files
        import bitcoinlib
        from bitcoinlib.config.opcodes import opcodes, opcodenames, OP_N_CODES
        bitcoinlib.transactions.opcodes = opcodes
        bitcoinlib.transactions.opcodenames = opcodenames
        bitcoinlib.transactions.OP_N_CODES = OP_N_CODES
    except ImportError:
        pass


def script_type_default(witness_type, multisig=False, locking_script=False):
    """
    Determine default script type for provided witness type and key type combination used in this library.
    :param witness_type: Type of wallet: standard or segwit
    :type witness_type: str
    :param multisig: Multisig key or not, default is False
    :type multisig: bool
    :param locking_script: Limit search to locking_script. Specify False for locking scripts and True
    for unlocking scripts
    :type locking_script: bool
    :return str: Default script type
    """

    if witness_type == 'legacy' and not multisig:
        return 'p2pkh' if locking_script else 'sig_pubkey'
    elif witness_type == 'legacy' and multisig:
        return 'p2sh' if locking_script else 'p2sh_multisig'
    elif witness_type == 'segwit' and not multisig:
        return 'p2wpkh' if locking_script else 'sig_pubkey'
    elif witness_type == 'segwit' and multisig:
        return 'p2wsh' if locking_script else 'p2sh_multisig'
    elif witness_type == 'p2sh-segwit' and not multisig:
        return 'p2sh' if locking_script else 'p2sh_p2wpkh'
    elif witness_type == 'p2sh-segwit' and multisig:
        return 'p2sh' if locking_script else 'p2sh_p2wsh'
    else:
        raise KeyError("Wallet and key type combination not supported: %s / %s" % (witness_type, multisig))
