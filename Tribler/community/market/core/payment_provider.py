import os
import json

from Tribler.dispersy.candidate import Candidate
from bitcoin_address import BitcoinAddress
from price import Price
from quantity import Quantity


class InsufficientFunds(Exception):
    """Used for throwing exception when there isn't sufficient funds available to transfer"""
    pass


class BitcoinPaymentProvider(object):
    """"Bitcoin payment provider which enables checking the bitcoin balance of this peer and transferring bitcoin to
    other bitcoin addresses through the electrum command line"""

    BITCOIN_MULTIPLIER = 1000

    def transfer_bitcoin(self, bitcoin_address, price):
        """
        Transfers the selected price in bitcoin to another bitcoin address if there is sufficient bitcoin

        :param bitcoin_address: Bitcoin address of the receiver of the bitcoin
        :param quantity: Price to be transferred
        :raises InsufficientFunds: Thrown when there isn't sufficient bitcoin to transfer
        """
        assert isinstance(bitcoin_address, BitcoinAddress), type(bitcoin_address)
        assert isinstance(price, Price), type(price)

        if self.balance() >= price:
            bitcoin_price = int(price) * self.BITCOIN_MULTIPLIER
            os.system('electrum payto -f 0 ' + str(bitcoin_address) + ' ' + str(bitcoin_price))
        else:
            raise InsufficientFunds()

    def balance(self):
        """
        :rtype: Price
        """
        data = json.loads(os.system('electrum getbalance'))

        balance = 0.0
        if 'confirmed' in data:
            return Price(int(float(data['confirmed']) * self.BITCOIN_MULTIPLIER))
        else:
            return Price(0)


class MultiChainPaymentProvider(object):
    """"Multi chain payment provider which enables checking the multi chain balance of this peer and transferring multi
    chain to other peers"""

    MULTI_CHAIN_MULTIPLIER = 100

    def __init__(self, multi_chain_community, public_key):
        """
        :param multi_chain_community: The multi chain community which manages multi chain transfers
        :param public_key: The public key of this peer
        """
        assert isinstance(public_key, str), type(public_key)

        super(MultiChainPaymentProvider, self).__init__()

        self.multi_chain_community = multi_chain_community
        self.public_key = public_key

    def transfer_multi_chain(self, candidate, quantity):
        """
        Transfers the selected quantity in multi chain coin to another peer if there is sufficient multi chain coin

        :param candidate: Receiver of the multi chain coin
        :param quantity: Quantity to be transferred
        :raises InsufficientFunds: Thrown when there isn't sufficient multi chain coin to transfer
        """
        assert isinstance(candidate, Candidate), type(candidate)
        assert isinstance(quantity, Quantity), type(quantity)

        if self.balance() >= quantity:
            byte_quantity = int(quantity) * self.MULTI_CHAIN_MULTIPLIER
            self.multi_chain_community.schedule_block(candidate, -byte_quantity, byte_quantity)
        else:
            raise InsufficientFunds()

    def balance(self):
        """
        :rtype: Quantity
        """
        total = self.multi_chain_community.persistence.get_total(self.public_key)

        if total == (-1, -1):
            return Quantity(0)
        else:
            return Quantity((max(0, total[0] - total[1]) / 2) / self.MULTI_CHAIN_MULTIPLIER)
