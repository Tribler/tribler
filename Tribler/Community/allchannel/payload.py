from Tribler.Core.dispersy.payload import Payload

class PropagateTorrentsPayload(Payload):
    """
    Propagate a list a infohashes for wich the sender has the .torrent files, and possibly metadata.
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohashes):
            assert isinstance(infohashes, (tuple, list))
            assert not filter(lambda x: not isinstance(x, str), infohashes)
            assert not filter(lambda x: not len(x) == 20, infohashes)
            assert len(infohashes) > 0
            super(PropagateTorrentsPayload.Implementation, self).__init__(meta)
            self._infohashes = infohashes

        @property
        def infohashes(self):
            return self._infohashes

class ChannelCastPayload(Payload):
    """
    Propagate semi random channel data.

    One channel-propagate message could contain a list with the following ChannelCommunity packets:
     - channel
     - torrent
     - comment
     - modify
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, packets):
            if __debug__:
                from Tribler.Core.dispersy.message import Packet
            assert isinstance(packets, list)
            assert not filter(lambda x: not isinstance(x, str), packets)
            assert not filter(lambda x: not len(x) >= 22, packets)
            super(ChannelCastPayload.Implementation, self).__init__(meta)
            self._packets = packets

        @property
        def packets(self):
            return self._packets

# class TorrentRequestPayload(Payload):
#     """
#     Request to download one .torrent files and metadata associated with a single infohash.
#     """
#     class Implementation(Payload.Implementation):
#         def __init__(self, meta, infohash):
#             assert isinstance(infohash, str)
#             assert len(infohash) == 20
#             super(TorrentRequestPayload.Implementation, self).__init__(meta)
#             self._infohash = infohash

#         @property
#         def infohash(self):
#             return self._infohash

# class TorrentResponsePayload(Payload):
#     """
#     Response to torrent-request message, will send back the .torrent file and, when available,
#     channel messages with metadata.
#     """
#     class Implementation(Payload.Implementation):
#         def __init__(self, meta, infohash, torrent_data, messages=[]):
#             assert isinstance(infohash, str)
#             assert len(infohash) == 20
#             assert isinstance(torrent_data, str)
#             assert isinstance(messages, (tuple, list))
#             assert not filter(lambda x: not isinstance(x, Message), messages)
#             assert not filter(lambda x: not x.name in (u"channel", u"torrent", u"modify"), messages)
#             self._infohash = infohash
#             self._torrent_data = torrent_data
#             self._messages = messages

#         @property
#         def infohash(self):
#             return self._infohash

#         @property
#         def torrent_data(self):
#             return self._torrent_data

#         @property
#         def messages(self):
#             return self._messages

#         @property
#         def footprint(self):
#             return "TorrentResponsePayload:" + self._infohash.encode("HEX")

#     def generate_footprint(self, infohash):
#         assert isinstance(infohash, str)
#         assert len(infohash) == 20
#         return "TorrentResponsePayload:" + infohash.encode("HEX")

class ChannelSearchRequestPayload(Payload):
    """
    Request a node to search for channels.

    Search can be performed in various ways depending on the method parameter:

     - simple-any-keyword: a match is made when any one of the keywords matches.  The keywords are
       given by the search parameter as a list of unicode lowercase strings.  Priority is given to
       results that (1) match more keywords, (2) match keywords earlier in the list, and (3) follow
       the ordering in the keywords list.

     - simple-all-keywords: a match is made when all the keywords match.  The keywords are given by
       the search parameter as a list of unicode lowercase strings.  Priority is given to results
       that more closely follow the ordering in the keywords list.

    Other search methodss may become available in the future.  We are thinking about regular
    expressions, how to handle filtering for unicode special charaters, etc.
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, skip, search, method=u"simple-any-keyword"):
            if __debug__:
                from Tribler.Core.dispersy.bloomfilter import BloomFilter
            assert isinstance(skip, BloomFilter)
            assert len(skip) <= 1024
            assert isinstance(search, (tuple, list))
            assert not filter(lambda x: not isinstance(x, unicode), search)
            assert isinstance(method, unicode)
            assert method in (u"simple-any-keyword", u"simple-all-keywords")
            super(ChannelSearchRequestPayload.Implementation, self).__init__(meta)
            self._skip = skip
            self._search = search
            self._method = method

        @property
        def skip(self):
            return self._skip

        @property
        def search(self):
            return self._search

        @property
        def method(self):
            return self._method

class ChannelSearchResponsePayload(Payload):
    """
    Response to a channel-search-request message, sending back a list of matching channels, some
    metadata, and a selection of available torrents.

    A search should result in a response containing a list of messages:

     - one or more 'channel' messages.  each will contain basic information such as channel name and
       description.

     - one or more 'torrent' messages.  each will contain basic information on a torrent, such as
       the infohash, that is available in a returned channel.

     - one or more 'modify' messages.  each will contain an update to either the channel or torent
       metadata, such as a new channel description or a torrent name.

    Note that messages can also contain a Packet instances.  This should reduce the load on the
    system when we do not have packet decoded already.
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, request_identifier, messages):
            if __debug__:
                from Tribler.Core.dispersy.message import Packet
            assert isinstance(request_identifier, str)
            assert len(request_identifier) == 20
            assert isinstance(messages, (tuple, list))
            assert not filter(lambda x: not isinstance(x, Packet), messages)
            assert not filter(lambda x: not x.name in (u"channel", u"torrent", u"modify"), messages)
            super(ChannelSearchResponsePayload.Implementation, self).__init__(meta)
            self._request_identifier = request_identifier
            self._messages = messages

        @property
        def request_identifier(self):
            return self._request_identifier

        @property
        def messages(self):
            return self._messages

        @property
        def footprint(self):
            return "ChannelSearchResponsePayload:" + self._request_identifier.encode("HEX")

    def generate_footprint(self, request_identifier):
        assert isinstance(request_identifier, str)
        assert len(request_identifier) == 20
        return "ChannelSearchResponsePayload:" + request_identifier.encode("HEX")
