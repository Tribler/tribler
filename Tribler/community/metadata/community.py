
from Tribler.dispersy.community import Community


class MetadataCommunity(Community):

    def __init__(self, dispersy, master, integrate_with_tribler=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._integrate_with_tribler = integrate_with_tribler

        super(MetadataCommunity, self).__init__(dispersy, master)

        if self._integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import ChannelCastDBHandler, PeerDBHandler

            # tribler channelcast database
            self._peer_db = PeerDBHandler.getInstance()


    def initiate_meta_messages(self):
        return [Message(self, u"metadata", MemberAuthentication(encoding="sha1"), PublicResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128, ), CommunityDestination(node_count=10), MetadataPayload(), self.check_metadata, self.on_metadata),
                ]


    def check_metadata(self, messages):
        pass


    def on_metadata(self, messages):
        pass
