from Tribler.Community.channel.community import ChannelCommunity

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

    def _initialize_meta_messages(self):
        super(PreviewChannelCommunity, self)._initialize_meta_messages()

        # remove unnecessary messages
        meta_messages = self._meta_messages
        self._meta_messages = {}
        for name in [u"dispersy-identity",
                     u"dispersy-identity-request",
                     u"dispersy-destroy-community",

                     u"channel",
                     u"torrent",
                     u"playlist",
                     u"comment",
                     u"modification",
                     u"playlist_torrent",
                     ]:
            self._meta_messages[name] = meta_messages[name]

    @property
    def dispersy_sync_initial_delay(self):
        # we are not joining a community, hence we do not use dispersy-sync
        return 0.0

    @property
    def dispersy_candidate_request_initial_delay(self):
        # we are not joining a community, hence we do not use dispersy-candidate-request
        return 0.0
