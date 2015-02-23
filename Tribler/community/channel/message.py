from Tribler.dispersy.message import DelayMessage


class DelayMessageReqChannelMessage(DelayMessage):

    """
    Raised during ChannelCommunity.check_ if the channel message has not been received yet.
    """

    def __init__(self, delayed, includeSnapshot=False):
        super(DelayMessageReqChannelMessage, self).__init__(delayed)
        if __debug__:
            from Tribler.dispersy.message import Message
        assert isinstance(delayed, Message.Implementation)
        self._includeSnapshot = includeSnapshot

    @property
    def match_info(self):
        return (self._cid, u"channel", None, None, []),

    def send_request(self, community, candidate):
        self._community.disp_create_missing_channel(candidate, self._includeSnapshot)
