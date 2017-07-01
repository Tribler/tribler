from random import randint

from hashlib import sha256

from Tribler.Core.Utilities.encoding import encode
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.dispersy.crypto import ECCrypto


class TriblerTestBlock(TriblerChainBlock):
    """
    Test Block that simulates a block used in TriblerChain.
    Also used in other test files for TriblerChain.
    """

    def __init__(self, previous=None, transaction=None):
        super(TriblerTestBlock, self).__init__()
        crypto = ECCrypto()
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        transaction = transaction or {'up': randint(201, 220), 'down': randint(221, 240)}

        if 'total_up' not in self.transaction:
            transaction['total_up'] = randint(241, 260)
        if 'total_down' not in self.transaction:
            transaction['total_down'] = randint(261, 280)

        if previous:
            self.key = previous.key
            transaction['total_up'] = previous.transaction['total_up'] + transaction['up']
            transaction['total_down'] = previous.transaction['total_down'] + transaction['down']
            TriblerChainBlock.__init__(self, (encode(transaction), previous.public_key, previous.sequence_number + 1,
                                              other, 0, previous.hash, 0, 0))
        else:
            self.key = crypto.generate_key(u"curve25519")
            TriblerChainBlock.__init__(self, (
                encode(transaction), self.key.pub().key_to_bin(), randint(50, 100), other, 0,
                sha256(str(randint(0, 100000))).digest(), 0, 0))
        self.sign(self.key)
