from Tribler.dispersy.crypto import ECCrypto
from Tribler.community.multichain.block import MultiChainBlock, GENESIS_ID, EMPTY_SIG
from Tribler.Test.test_multichain_utilities import MultiChainTestCase, TestBlock


class TestBlocks(MultiChainTestCase):
    def __init__(self, *args, **kwargs):
        super(TestBlocks, self).__init__(*args, **kwargs)

    def test_hash(self):
        block = MultiChainBlock()
        self.assertEqual(block.hash, 'r\x90\x9fV2\xcb\x9bi\xdd\x888\x11\x9eK\xf6.\xa2\x8c{\xc1\xb5|4w\xd5\xf6\xf0\xfcS'
                                     '\x16<\xb3')

    def test_sign(self):
        crypto = ECCrypto()
        block = TestBlock()
        self.assertTrue(crypto.is_valid_signature(block.key, block.pack(signature=False), block.signature))

    def test_create_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = self.MockDatabase()
        block = MultiChainBlock.create(db, key.pub().key_to_bin(), link=None)
        self.assertEqual(block.previous_hash, GENESIS_ID)
        self.assertEqual(block.sequence_number, 1)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.signature, EMPTY_SIG)

    def test_create_next(self):
        db = self.MockDatabase()
        prev = TestBlock()
        prev.sequence_number = 1
        db.add_block(prev)
        block = MultiChainBlock.create(db, prev.public_key, link=None)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)

    def test_create_link_genesis(self):
        key = ECCrypto().generate_key(u"curve25519")
        db = self.MockDatabase()
        link = TestBlock()
        db.add_block(link)
        block = MultiChainBlock.create(db, key.pub().key_to_bin(), link=link)
        self.assertEqual(block.previous_hash, GENESIS_ID)
        self.assertEqual(block.sequence_number, 1)
        self.assertEqual(block.public_key, key.pub().key_to_bin())
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_create_link_next(self):
        db = self.MockDatabase()
        prev = TestBlock()
        prev.sequence_number = 1
        db.add_block(prev)
        link = TestBlock()
        db.add_block(link)
        block = MultiChainBlock.create(db, prev.public_key, link=link)
        self.assertEqual(block.previous_hash, prev.hash)
        self.assertEqual(block.sequence_number, 2)
        self.assertEqual(block.public_key, prev.public_key)
        self.assertEqual(block.link_public_key, link.public_key)
        self.assertEqual(block.link_sequence_number, link.sequence_number)

    def test_pack(self):
        block = MultiChainBlock()
        block.up = 1399791724
        block.down = 1869506336
        block.total_up = 7020658959671910766
        block.total_down = 7742567808708517985
        block.public_key = 'll the fish, so sad that it should come to this. We tried to warn you all '
        block.sequence_number = 1651864608
        block.link_public_key = 'oh dear! You may not share our intellect, which might explain your disresp'
        block.link_sequence_number = 1701016620
        block.previous_hash = ' for all the natural wonders tha'
        block.signature = 't grow around you. So long, so long and thanks for all the fish!'
        self.assertEqual(block.pack(), 'So long and thanks for all the fish, so sad that it should come to this. We '
                                       'tried to warn you all but oh dear! You may not share our intellect, which '
                                       'might explain your disrespect, for all the natural wonders that grow around '
                                       'you. So long, so long and thanks for all the fish!')

    def test_unpack(self):
        block = MultiChainBlock.unpack('So long and thanks for all the fish, so sad that it should come to this. We '
                                       'tried to warn you all but oh dear! You may not share our intellect, which '
                                       'might explain your disrespect, for all the natural wonders that grow around '
                                       'you. So long, so long and thanks for all the fish!')
        self.assertEqual(block.up, 1399791724)
        self.assertEqual(block.down, 1869506336)
        self.assertEqual(block.total_up, 7020658959671910766)
        self.assertEqual(block.total_down, 7742567808708517985)
        self.assertEqual(block.public_key, 'll the fish, so sad that it should come to this. We tried to warn you all ')
        self.assertEqual(block.sequence_number, 1651864608)
        self.assertEqual(block.link_public_key,
                         'oh dear! You may not share our intellect, which might explain your disresp')
        self.assertEqual(block.link_sequence_number, 1701016620)
        self.assertEqual(block.previous_hash, ' for all the natural wonders tha')
        self.assertEqual(block.signature, 't grow around you. So long, so long and thanks for all the fish!')

    # TODO: test validate

    class MockDatabase(object):
        def __init__(self, *args, **kwargs):
            super(TestBlocks.MockDatabase, self).__init__(*args, **kwargs)
            self.data = dict()

        def add_block(self, block):
            if self.data.get(block.public_key) is None:
                self.data[block.public_key] = []
            self.data[block.public_key].append(block)
            self.data[block.public_key].sort(key=lambda b: b.sequence_number)

        def get_latest(self, pk):
            return self.data[pk][-1] if self.data.get(pk) else None
