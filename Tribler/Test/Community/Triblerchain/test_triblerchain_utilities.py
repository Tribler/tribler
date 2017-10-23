import random

from hashlib import sha256

from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.dispersy.crypto import ECCrypto


class TriblerTestBlock(TriblerChainBlock):
    """
    Test Block that simulates a block used in TriblerChain.
    Also used in other test files for TriblerChain.
    """

    def __init__(self, previous=None):

        crypto = ECCrypto()
        other = crypto.generate_key(u"curve25519").pub().key_to_bin()

        self.transaction = [random.randint(201, 220), random.randint(221, 240), 0, 0]

        if previous:
            self.total_up = previous.total_up + self.up
            self.total_down = previous.total_down + self.down
            self.key = previous.key
            super(TriblerTestBlock, self).__init__(data=(previous.public_key, previous.sequence_number + 1,
                                                         other, 0, previous.hash, 0, 0))
        else:
            self.total_up = random.randint(241, 260)
            self.total_down = random.randint(261, 280)
            self.key = crypto.generate_key(u"curve25519")
            super(TriblerTestBlock, self).__init__(data=(self.key.pub().key_to_bin(), random.randint(50, 100), other, 0,
                                                         sha256(str(random.randint(0, 100000))).digest(), 0, 0))
        self.sign(self.key)
