import unittest

from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository
from Tribler.community.market.core.message import MessageId, TraderId, MessageNumber


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
        self.memory_message_repository = MemoryMessageRepository('trader_id')

    def test_next_identity(self):
        # Test for next identity
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('1')),
                          self.memory_message_repository.next_identity())


if __name__ == '__main__':
    unittest.main()
