from Tribler.community.channel.community import ChannelCommunity
from random import sample

class PreviewChannelCommunity(ChannelCommunity):
    """
    The PreviewChannelCommunity extends the ChannelCommunity to allow ChannelCommunity messages to
    be decoded while not actually joining or participating in an actual ChannelCommunity.
    """

    @property
    def dispersy_enable_candidate_walker(self):
        return False

    def get_channel_mode(self):
        return ChannelCommunity.CHANNEL_CLOSED, False

    #AllChannel functions
    def selectTorrentsToCollect(self, infohashes):
        to_collect = ChannelCommunity.selectTorrentsToCollect(self, infohashes)

        #Reducing the number of samples to collect for unsubscribed channels
        if len(to_collect) > 2:
            return sample(to_collect, 2)
        return to_collect
