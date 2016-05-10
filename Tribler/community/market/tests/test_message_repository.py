import unittest

from Tribler.community.market.core.message_repository import MessageRepository, MemoryMessageRepository
from Tribler.community.market.core.tick import MessageId, TraderId, MessageNumber


class MessageRepositoryTestSuite(unittest.TestCase):
    """Message repository test cases."""

    def test_message_repository(self):
        # Object creation
        message_repository = MessageRepository()

        # Test for next identity
        self.assertEquals(NotImplemented, message_repository.next_identity())

    def test_memory_message_repository(self):
        # Object creation
        memory_message_repository = MemoryMessageRepository('trader_id')
        message_id = MessageId(TraderId('trader_id'), MessageNumber('1'))

        # Test for next identity
        self.assertEquals(message_id, memory_message_repository.next_identity())


if __name__ == '__main__':
    unittest.main()
