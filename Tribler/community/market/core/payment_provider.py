from Tribler.dispersy.candidate import Candidate
from quantity import Quantity


class InsufficientFunds(Exception):
    """Used for throwing exception when there isn't sufficient funds available to transfer"""
    pass


class MultiChainPaymentProvider(object):
    """"Multi chain payment provider which enables checking the multi chain balance of this peer and transferring multi
    chain to other peers"""

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

        byte_quantity = int(quantity) * 100

        if int(self.balance()) * 100 >= byte_quantity:
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
            return Quantity((max(0, total[0] - total[1]) / 2) / 100)
