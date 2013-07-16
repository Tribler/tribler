from Tribler.community.channel.community import ChannelCommunity
from time import time
from random import sample


class PreviewChannelCommunity(ChannelCommunity):

    """
    The PreviewChannelCommunity extends the ChannelCommunity to allow ChannelCommunity messages to
    be decoded while not actually joining or participating in an actual ChannelCommunity.
    """

    def __init__(self, *args, **kargs):
        super(PreviewChannelCommunity, self).__init__(*args, **kargs)
        self.init_timestamp = time()

    @property
    def dispersy_enable_bloom_filter_sync(self):
        # 1. disable bloom filter sync in walker
        # 2. accept messages in any global time range
        return False

    @property
    def dispersy_enable_candidate_walker(self):
        return False

    def get_channel_mode(self):
        return ChannelCommunity.CHANNEL_CLOSED, False
