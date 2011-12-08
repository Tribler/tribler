from Tribler.community.channel.community import ChannelCommunity
from random import sample

class PreviewChannelCommunity(ChannelCommunity):
    """
    The PreviewChannelCommunity extends the ChannelCommunity to allow ChannelCommunity messages to
    be decoded while not actually joining or participating in an actual ChannelCommunity.
    """
    # the database default for auto_load is always True regardless
    # @classmethod
    # def join_community(cls, *args, **kargs):
    #     community = super(PreviewChannelCommunity, self).join_community(*args, **kargs)
    #     community.dispersy_auto_load = True
    #     return community

    # def _initialize_meta_messages(self):
    #     super(PreviewChannelCommunity, self)._initialize_meta_messages()

    #     # remove unnecessary messages
    #     meta_messages = self._meta_messages
    #     self._meta_messages = {}
    #     for name in [u"dispersy-identity",
    #                  u"dispersy-missing-identity",
    #                  u"dispersy-destroy-community",
    #                  u"dispersy-authorize",
    #                  u"dispersy-missing-proof",
    #                  u"dispersy-revoke",
    #                  u"dispersy-dynamic-settings",
    #                  # u"dispersy-undo-other",
    #                  # u"dispersy-undo-own",

    #                  u"channel",
    #                  u"torrent",
    #                  u"playlist",
    #                  u"comment",
    #                  u"modification",
    #                  u"playlist_torrent",
    #                  u"moderation",
    #                  u"mark_torrent",
    #                  u"missing-channel",
    #                  ]:
    #         self._meta_messages[name] = meta_messages[name]

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