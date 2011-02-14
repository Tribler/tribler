from conversion import AllChannelConversion
from payload import PropagateTorrentsPayload, TorrentRequestPayload

from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler

from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.resolution import PublicResolution
from Tribler.Core.dispersy.distribution import DirectDistribution
from Tribler.Core.dispersy.destination import AddressDestination, CommunityDestination

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class AllChannelCommunity(Community):
    """
    A single community that all Tribler members join and use to disseminate .torrent files.

    The dissemination of .torrent files, using 'propagate-torrents' messages, is NOT done using a
    dispersy sync mechanism.  We prefer more specific dissemination mechanism than dispersy allows.
    Dissemination occurs by periodically sending:

     - N most recently received .torrent files
     - M random .torrent files
     - O most recent .torrent files, created by ourselves
     - P randomly choosen .torrent files, created by ourselves
    """

    def __init__(self, cid):
        super(AllChannelCommunity, self).__init__(cid)

        # community specific database
        self._torrent_database = TorrentDBHandler.getInstance()

        # mapping
        self._incoming_message_map = {u"propagate-torrents":self.on_propagate_torrents,
                                      u"torrent-request":self.on_torrent_request}

        # add the Dispersy message handlers to the _incoming_message_map
        for message, handler in self._dispersy.get_message_handlers(self):
            assert message.name not in self._incoming_message_map
            self._incoming_message_map[message.name] = handler

        # available conversions
        self.add_conversion(AllChannelConversion(self), True)

    @property
    def dispersy_sync_interval(self):
        # because there is nothing to sync in this community, we will only 'sync' once per hour
        return 3600.0

    def initiate_meta_messages(self):
        return [Message(self, u"propagate-torrents", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), PropagateTorrentsPayload()),
                Message(self, u"torrent-request", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentRequestPayload())]

    def create_propagate_torrents(self, store_and_forward=True):
        """
        Create a 'propagate-torrents' message.

        The message contains one or more infohashes that we want to propagate.
        """
        assert isinstance(store_and_forward, bool)

        # N most recently received .torrent files
        # M random .torrent files
        # O most recent .torrent files, created by ourselves
        # P randomly choosen .torrent files, created by ourselves
        infohashes = [infohash.decode("BASE64") for infohash, in self._torrent_database._db.fetchall(u"SELECT infohash FROM Torrent ORDER BY RANDOM() LIMIT 50")]

        meta = self.get_meta_message(u"propagate-torrents")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohashes))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def on_propagate_torrents(self, address, message):
        """
        Received a 'propagate-torrents' message.
        """
        if __debug__: dprint(message)
        fetchone = self._torrent_database._db.fetchone
        for infohash in message.payload.infohashes:
            if not fetchone(u"SELECT 1 FROM Torrent WHERE infohash = ?", (infohash,)):
                self.create_torrent_request(address, infohash)

    def create_torrent_request(self, address, infohash, store_and_forward=True):
        """
        Create a message to request a .torrent file.
        """
        assert isinstance(infohash, str)
        assert len(infohash) == 20
        assert isinstance(store_and_forward, bool)

        meta = self.get_meta_message(u"torrent-request")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(address),
                                 meta.payload.implement(infohash))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def on_torrent_request(self, address, message):
        """
        Received a 'torrent-request' message.
        """
        dprint("TODO")

    def on_message(self, address, message):
        """
        Decide which function to feed the message to.
        """
        if self._timeline.check(message):
            self._incoming_message_map[message.name](address, message)
        else:
            raise DropMessage("TODO: implement delay by proof")
