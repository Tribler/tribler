from __future__ import absolute_import

import abc
import logging
import random
import string

from ipv8.taskmanager import TaskManager

import six


class InsufficientFunds(Exception):
    """
    Used for throwing exception when there isn't sufficient funds available to transfer assets.
    """
    pass


class Wallet(six.with_metaclass(abc.ABCMeta, TaskManager)):
    """
    This is the base class of a wallet and contains various methods that every wallet should implement.
    To create your own wallet, subclass this class and implement the required methods.
    """
    def __init__(self):
        super(Wallet, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.created = False
        self.unlocked = False

    def generate_txid(self, length=10):
        """
        Generate a random transaction ID
        """
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    @abc.abstractmethod
    def get_identifier(self):
        return

    @abc.abstractmethod
    def get_name(self):
        return

    @abc.abstractmethod
    def create_wallet(self, *args, **kwargs):
        return

    @abc.abstractmethod
    def get_balance(self):
        return

    @abc.abstractmethod
    def transfer(self, *args, **kwargs):
        return

    @abc.abstractmethod
    def get_address(self):
        return

    @abc.abstractmethod
    def get_transactions(self):
        return

    @abc.abstractmethod
    def min_unit(self):
        return

    @abc.abstractmethod
    def precision(self):
        """
        The precision of an asset inside a wallet represents the number of digits after the decimal.
        For fiat currency, the precision would be 2 since the minimum unit is often 0.01.
        """
        return
