from Tribler.community.channel.community import ChannelCommunity

class PreviewChannelCommunity(ChannelCommunity):
    """
    The PreviewChannelCommunity extends the ChannelCommunity to allow ChannelCommunity messages to
    be decoded while not actually joining or participating in an actual ChannelCommunity.
    """

    @property
    def dispersy_acceptable_global_time_range(self):
        # we will accept the full 64 bit global time range
        return 2**64 - self._global_time

    @property
    def dispersy_enable_candidate_walker(self):
        return False