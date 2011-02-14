class Resolution(object):
    def setup(self, message):
        """
        Setup is called after the meta message is initially created.
        """
        if __debug__:
            from message import Message
        assert isinstance(message, Message)

class PublicResolution(Resolution):
    pass

class LinearResolution(Resolution):
    pass

