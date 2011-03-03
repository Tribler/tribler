from hashlib import sha1

from conversion import AllChannelConversion
from payload import PropagateTorrentsPayload, ChannelSearchRequestPayload, ChannelSearchResponsePayload

from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler
from Tribler.Core.SocialNetwork.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Core.dispersy.bloomfilter import BloomFilter
from Tribler.Core.dispersy.dispersydatabase import DispersyDatabase
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.authentication import NoAuthentication
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
    @classmethod
    def load_communities(cls, my_member, *args, **kargs):
        """
        Returns a list with all AllChannelCommunity instances that we are part off.

        Since there is one global AllChannelCommunity, we will return one using a static public
        master member key.
        """
        communities = super(AllChannelCommunity, cls).load_communities(*args, **kargs)

        if not communities:
            master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403b2c94642d3a2228c2f274dcac5ddebc1b36da58282931b960ac19b0c1238bc8d5a17dfeee037ef3c320785fea6531f9bd498000643a7740bc182fae15e0461b158dcb9b19bcd6903f4acc09dc99392ed3077eca599d014118336abb372a9e6de24f83501797edc25e8f4cce8072780b56db6637844b394c90fc866090e28bdc0060831f26b32d946a25699d1e8a89b".decode("HEX")

            dispersy_database = DispersyDatabase.get_instance()
            dispersy_database.execute(u"INSERT OR IGNORE INTO community (user, classification, public_key) VALUES (?, ?, ?)",
                                      (my_member.database_id, cls.get_classification(), buffer(master_key)))

            # new community instance
            community = cls(master_key, *args, **kargs)

            # send out my initial dispersy-identity
            community.create_identity()

            # add new community
            communities.append(community)

        return communities

    def __init__(self, master_key):
        super(AllChannelCommunity, self).__init__(master_key)

        # tribler torrent database
        self._torrent_database = TorrentDBHandler.getInstance()

        # tribler remote torrent handler
        self._remote_torrent_handler = RemoteTorrentHandler.getInstance()

        # # a queue with infohashes that we might want to download in the near future
        # self._torrent_request_queue = []
        # self._torrent_request_outstanding = False

    @property
    def dispersy_sync_interval(self):
        # because there is nothing to sync in this community, we will only 'sync' once per hour
        return 3600.0

    def initiate_meta_messages(self):
        return [Message(self, u"propagate-torrents", NoAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), PropagateTorrentsPayload(), self.check_propagate_torrents, self.on_propagate_torrents),
                # Message(self, u"torrent-request", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentRequestPayload()),
                # Message(self, u"torrent-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), TorrentResponsePayload()),
                Message(self, u"channel-search-request", NoAuthentication(), PublicResolution(), DirectDistribution(), CommunityDestination(node_count=10), ChannelSearchRequestPayload(), self.check_channel_search_request, self.on_channel_search_request),
                Message(self, u"channel-search-response", NoAuthentication(), PublicResolution(), DirectDistribution(), AddressDestination(), ChannelSearchResponsePayload(), self.check_channel_search_response, self.on_channel_search_response),
                ]

    def initiate_conversions(self):
        return [AllChannelConversion(self)]

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
        # todo: niels, please select the infohashes you want

        meta = self.get_meta_message(u"propagate-torrents")
        message = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(infohashes))

        if store_and_forward:
            self._dispersy.store_and_forward([message])

        return message

    def check_propagate_torrents(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_propagate_torrents(self, address, message):
        """
        Received a 'propagate-torrents' message.
        """
        if __debug__: dprint(message)
        for infohash in message.payload.infohashes:
            # self._torrent_request_queue.append((address, infohash))
            # if __debug__: dprint("there are ", len(self._torrent_request_queue), " infohashes in the queue")

            pass
            # todo: niels? select the infohashes that we want to download
            # for infohash in message.payload.infohashes:
            #     self._remote_torrent_handler.download_torrent(permid, infohash, lambda *args: pass)

    #         self._start_torrent_request_queue()

    # def _start_torrent_request_queue(self):
    #     # check that we are not working on a request already
    #     if not self._torrent_request_outstanding:
    #         while True:
    #             if not self._torrent_request_queue:
    #                 if __debug__: dprint("no more infohashes outstanding")
    #                 return

    #             address, infohash = self._torrent_request_queue.pop(0)
    #             if self._torrent_database._db.fetchone(u"SELECT 1 FROM Torrent WHERE infohash = ?", (infohash,)):
    #                 if __debug__: dprint("we already have this infohash")
    #                 continue

    #             # found an infohash to request
    #             break

    #         self.create_torrent_request(address, infohash, self._fulfill_torrent_request, (address,))
    #         self._torrent_request_outstanding = True

    # def _fulfill_torrent_request(self, address, message, req_address):
    #     if message:
    #         # todo: handle torrent insert
    #         pass

    #     else:
    #         # timeout on a request to req_address.  all requests to this address will likely
    #         # timeout, hence remove all these requests
    #         self._torrent_request_queue = [(address, infohash) for address, infohash in self._torrent_request_queue if not address == req_address]

    #     self._torrent_request_outstanding = False
    #     self._start_torrent_request_queue()

    # def create_torrent_request(self, address, infohash, response_func, response_args=(), timeout=10.0, store_and_forward=True):
    #     """
    #     Create a message to request a .torrent file.
    #     """
    #     assert isinstance(infohash, str)
    #     assert len(infohash) == 20
    #     assert hasattr(response_func, "__call__")
    #     assert isinstance(response_args, tuple)
    #     assert isinstance(timeout, float)
    #     assert timeout > 0.0
    #     assert isinstance(store_and_forward, bool)

    #     meta = self.get_meta_message(u"torrent-request")
    #     request = meta.implement(meta.authentication.implement(),
    #                              meta.distribution.implement(self._timeline.global_time),
    #                              meta.destination.implement(address),
    #                              meta.payload.implement(infohash))

    #     if store_and_forward:
    #         self._dispersy.store_and_forward([request])

    #     if response_func:
    #         meta = self.get_meta_message(u"torrent-response")
    #         footprint = meta.generate_footprint(payload=(infohash,))
    #         self._dispersy.await_message(footprint, response_func, response_args, timeout)

    #     return request

    # def on_torrent_request(self, address, message):
    #     """
    #     Received a 'torrent-request' message.
    #     """
    #     # we need to find the .torrent file and read the binary data
    #     torrent = self._torrent_database.getTorrent(message.payload.infohash)
    #     dprint(torrent, lines=1)
    #     if not (torrent and torrent["destination_path"] and os.path.isfile(torrent["destination_path"])):
    #         raise DropMessage("We do not have the requested infohash")
    #         return
    #     torrent_data = open(torrent["destination_path"], "r").read()

    #     # we need to find, optionally, some meta data such as associated 'channel', 'torrent', and
    #     # 'modify' messages.

    #     # todo: niels?
    #     # messages = [Message]

    #     meta = self.get_meta_message(u"torrent-response")
    #     response = meta.implement(meta.authentication.implement(),
    #                               meta.distribution.implement(self._timeline.global_time),
    #                               meta.destination.implement(address),
    #                               meta.payload.implement(message.payload.infohash, torrent_data, messages))

    #     self._dispersy.store_and_forward([message])

    # def on_torrent_response(self, address, message):
    #     """
    #     Received a 'torrent-response' message.
    #     """
    #     # we ignore this message because we get a different callback to match it to the request
    #     pass

    def create_channel_search_request(self, skip, search, response_func, response_args=(), timeout=10.0, method=u"simple-any-keyword", store_and_forward=True):
        """
        Create a message to request a remote channel search.
        """
        assert isinstance(skip, (tuple, list))
        assert not filter(lambda x: not isinstance(x, Message), skip)
        assert isinstance(search, (tuple, list))
        assert not filter(lambda x: not isinstance(x, unicode), search)
        assert isinstance(method, unicode)
        assert method in (u"simple-any-keyword", u"simple-all-keywords")
        assert hasattr(response_func, "__call__")
        assert isinstance(response_args, tuple)
        assert isinstance(timeout, float)
        assert timeout > 0.0
        assert isinstance(store_and_forward, bool)

        # todo: we need to set a max items in the bloom filter to limit the size.  the bloom filter
        # be no more than 1000 bytes large.
        skip_bloomfilter = BloomFilter(max(1, len(skip)), 0.1)
        map(skip_bloomfilter.add, (message.packet for message in skip))

        meta = self.get_meta_message(u"channel-search-request")
        request = meta.implement(meta.authentication.implement(),
                                 meta.distribution.implement(self._timeline.global_time),
                                 meta.destination.implement(),
                                 meta.payload.implement(skip_bloomfilter, search, method))

        if store_and_forward:
            self._dispersy.store_and_forward([request])

        if response_func:
            meta = self.get_meta_message(u"channel-search-response")
            footprint = meta.generate_footprint(payload=(sha1(request.packet).digest(),))
            self._dispersy.await_message(footprint, response_func, response_args, timeout)

        return request

    def check_channel_search_request(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_channel_search_request(self, address, request):
        """
        Received a 'channel-search-request' message.
        """
        # we need to find channels matching the search criteria

        packets = []

        # todo: niels?
        # packets = [packets]

        # we need to find, optionally, some meta data such as associated 'torrent', and 'modify'
        # messages.

        # todo: niels?
        # packets = [packets]

        meta = self.get_meta_message(u"channel-search-response")
        response = meta.implement(meta.authentication.implement(),
                                  meta.distribution.implement(self._timeline.global_time),
                                  meta.destination.implement(address),
                                  meta.payload.implement(sha1(request.packet).digest(), packets))

        self._dispersy.store_and_forward([response])

    def check_channel_search_response(self, address, message):
        if not self._timeline.check(message):
            raise DropMessage("TODO: implement delay by proof")

    def on_channel_search_response(self, address, message):
        """
        Received a 'channel-search-response' message.
        """
        # we ignore this message because we get a different callback to match it to the request
        pass
