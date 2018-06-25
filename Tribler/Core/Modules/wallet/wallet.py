import logging
import random
import string
import sys
from abc import ABCMeta, abstractmethod

import keyring

from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class InsufficientFunds(Exception):
    """
    Used for throwing exception when there isn't sufficient funds available to transfer assets.
    """
    pass


class Wallet(TaskManager):
    """
    This is the base class of a wallet and contains various methods that every wallet should implement.
    To create your own wallet, subclass this class and implement the required methods.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        super(Wallet, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.created = False
        self.unlocked = False

        # When there is no available keyring backend, we use an unencrypted keyring on Linux since an encrypted keyring
        # requires input from stdin.
        if sys.platform.startswith('linux'):
            from keyrings.alt.file import EncryptedKeyring, PlaintextKeyring
            if isinstance(keyring.get_keyring(), EncryptedKeyring):
                for new_keyring in keyring.backend.get_all_keyring():
                    if isinstance(new_keyring, PlaintextKeyring):
                        keyring.set_keyring(new_keyring)

    def generate_txid(self, length=10):
        """
        Generate a random transaction ID
        """
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    @abstractmethod
    def get_identifier(self):
        return

    @abstractmethod
    def get_name(self):
        return

    @abstractmethod
    def create_wallet(self, *args, **kwargs):
        return

    @abstractmethod
    def get_balance(self):
        return

    @abstractmethod
    def transfer(self, *args, **kwargs):
        return

    @abstractmethod
    def get_address(self):
        return

    @abstractmethod
    def get_transactions(self):
        return

    @abstractmethod
    def min_unit(self):
        return
