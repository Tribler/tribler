import logging


class ReputationManager(object):

    def __init__(self, blocks):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.blocks = blocks

    def compute(self, own_public_key):
        """
        Compute the reputation based on the data in the TrustChain database.
        """
        raise NotImplementedError()
