from Tribler.dispersy.message import DelayMessage
from Tribler.community.channel.community import ChannelCommunity


class DelayMessageReqChannelMessage(DelayMessage):

    """
    Raised during ChannelCommunity.check_ if the channel message has not been received yet.
    """

    def __init__(self, delayed, channel_community, includeSnapshot=False):
        super(DelayMessageReqChannelMessage, self).__init__(delayed)
        if __debug__:
            from Tribler.dispersy.message import Message
            assert isinstance(delayed, Message.Implementation), type(delayed)
            assert isinstance(channel_community, ChannelCommunity), type(channel_community)

        self._channel_community = channel_community
        self._includeSnapshot = includeSnapshot

    @property
    def match_info(self):
        # we return the channel_community cid here, to register the delay at that community
        return (self._channel_community.cid, u"channel", None, None, []),

    def send_request(self, community, candidate):
        # the request is sent from within the channel_community
        self._channel_community.disp_create_missing_channel(candidate, self._includeSnapshot)
