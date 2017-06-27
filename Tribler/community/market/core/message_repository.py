from Tribler.community.market.core.tick import TraderId, MessageNumber, MessageId


class MessageRepository(object):
    """A repository interface for messages in the order book"""

    def next_identity(self):
        return NotImplemented


class MemoryMessageRepository(MessageRepository):
    """A repository for messages in the order book stored in memory"""

    def __init__(self, mid):
        """
        :param mid: Hex encoded version of the member id of this node
        :type mid: str
        """
        super(MemoryMessageRepository, self).__init__()

        try:
            int(mid, 16)
        except ValueError:  # Not a hexadecimal
            raise ValueError("Encoded public key must be hexadecimal")

        self._mid = mid
        self._next_id = 0  # Counter to keep track of the number of messages created by this repository

    def next_identity(self):
        """
        :rtype: MessageId
        """
        self._next_id += 1
        return MessageId(TraderId(self._mid), MessageNumber(str(self._next_id)))
