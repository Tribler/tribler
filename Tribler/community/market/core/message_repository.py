from tick import TraderId, MessageNumber, MessageId


class MessageRepository(object):
    """A repository for messages in the order book"""

    def next_identity(self):
        """
        Return the next identity

        :return: The next available identity
        :rtype: MessageId
        """
        return NotImplemented


class MemoryMessageRepository(MessageRepository):
    """A repository for messages in the order book stored in memory"""

    def __init__(self, pubkey):
        """
        Initialise the MemoryMessageRepository

        :param pubkey: Hex encoded version of the public key of this node
        :type pubkey: str
        """
        super(MemoryMessageRepository, self).__init__()

        try:
            int(pubkey, 16)
        except ValueError:  # Not a hexadecimal
            raise ValueError("Encoded public key must be hexadecimal")

        self.pubkey = pubkey
        self._next_id = 0  # Counter to keep track of the number of messages created by this repository

    def next_identity(self):
        """
        Return the next identity

        :return: The next available identity
        :rtype: MessageId
        """
        self._next_id += 1
        return MessageId(TraderId(self.pubkey), MessageNumber(str(self._next_id)))
