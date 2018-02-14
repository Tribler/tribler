import unittest

from Tribler.community.market.core.message import MessageId, TraderId, MessageNumber
from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository


class MessageRepositoryTestSuite(unittest.TestCase):
    """Message repository test cases."""

    def setUp(self):
        # Object creation
        self.message_repository = MessageRepository()

    def test_next_identity(self):
        # Test for next identity
        self.assertEquals(NotImplemented, self.message_repository.next_identity())


class MemoryMessageRepositoryTestSuite(unittest.TestCase):
    """Memory message repository test cases."""

    def setUp(self):
        # Object creation
        self.memory_message_repository = MemoryMessageRepository('0')

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            MemoryMessageRepository('mid')

    def test_next_identity(self):
        # Test for next identity
        self.assertEquals(MessageId(TraderId('0'), MessageNumber(1)),
                          self.memory_message_repository.next_identity())
