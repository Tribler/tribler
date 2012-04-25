from Tribler.Core.dispersy.message import DelayMessage

class DelayMessageReqChannelMessage(DelayMessage):
    """
    Raised during ChannelCommunity.check_ if the channel message has not been received yet.
    """
    def __init__(self, delayed, community = None, includeSnapshot = False):
        if __debug__:
            from Tribler.Core.dispersy.message import Message
        assert isinstance(delayed, Message.Implementation)

        self._community = community or delayed.community
        self._includeSnapshot = includeSnapshot

        # the footprint that will trigger the delayed packet
        footprint = "".join(("channel", " Community:", self._community.cid.encode("HEX")))
        super(DelayMessageReqChannelMessage, self).__init__("Missing channel-message", footprint, delayed)

    @property
    def request(self):
        # the request message that asks for the message that will trigger the delayed packet
        meta = self._community.get_meta_message(u"missing-channel")
        return meta.impl(distribution=(self._community.global_time,),
                         destination=(self._delayed.candidate,),
                         payload=(self._includeSnapshot,))

