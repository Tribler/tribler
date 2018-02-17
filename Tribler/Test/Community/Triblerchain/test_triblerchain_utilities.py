import random

from hashlib import sha256

from Tribler.Core.Utilities.encoding import encode
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto


class TriblerTestBlock(TriblerChainBlock):
    """
    Test Block that simulates a block used in TriblerChain.
    Also used in other test files for TriblerChain.
    """

    def __init__(self, previous=None):
        super(TriblerTestBlock, self).__init__()
        crypto = ECCrypto()
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        transaction = {'up': random.randint(201, 220), 'down': random.randint(221, 240), 'total_up': 0, 'total_down': 0}

        if previous:
            self.key = previous.key
            transaction['total_up'] = previous.transaction['total_up'] + transaction['up']
            transaction['total_down'] = previous.transaction['total_down'] + transaction['down']
            TriblerChainBlock.__init__(self, (encode(transaction), previous.public_key, previous.sequence_number + 1,
                                              other, 0, previous.hash, 0, 0))
        else:
            transaction['total_up'] = random.randint(241, 260)
            transaction['total_down'] = random.randint(261, 280)
            self.key = crypto.generate_key(u"curve25519")
            TriblerChainBlock.__init__(self, (
                encode(transaction), self.key.pub().key_to_bin(), random.randint(50, 100), other, 0,
                sha256(str(random.randint(0, 100000))).digest(), 0, 0))
        self.sign(self.key)
