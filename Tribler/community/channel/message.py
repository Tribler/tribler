from Tribler.dispersy.message import DelayMessage

class DelayMessageReqChannelMessage(DelayMessage):
    """
    Raised during ChannelCommunity.check_ if the channel message has not been received yet.
    """
    def __init__(self, delayed, community = None, includeSnapshot = False):
        super(DelayMessageReqChannelMessage, self).__init__(delayed)
        if __debug__:
            from Tribler.dispersy.message import Message
        assert isinstance(delayed, Message.Implementation)

        self._community = community or delayed.community
        self._includeSnapshot = includeSnapshot

    def create_request(self):
        self._community.disp_create_missing_channel(self._delayed.candidate, self._includeSnapshot, self._process_delayed_message)

