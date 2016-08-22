from struct import pack, unpack_from
from random import choice, sample

from Tribler.community.basecommunity import BaseConversion
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.message import DropPacket, Message, BatchConfiguration
from Tribler.dispersy.payload import Payload
from Tribler.dispersy.resolution import PublicResolution

"""Backward compatibility for AllChannel.

    Usage:
        1. Create AllChannelCompatibility(newcommunity)
        2. Register compatibility.deprecated_meta_messages()
        3. Register AllChannelConversion

"""

class ChannelCastPayload(Payload):

    """
    Propagate semi random channel data.
    One channel-propagate message could contain a list with the following ChannelCommunity packets:
     - torrent
    """
    class Implementation(Payload.Implementation):

        def __init__(self, meta, torrents):
            if __debug__:
                assert isinstance(torrents, dict), 'torrents should be a dictionary containing cid:set(infohashes)'
                for cid, infohashes in torrents.iteritems():
                    assert isinstance(cid, str)
                    assert len(cid) == 20
                    assert isinstance(infohashes, set)
                    assert not filter(lambda x: not isinstance(x, str), infohashes)
                    assert not filter(lambda x: not len(x) == 20, infohashes)
                    assert len(infohashes) > 0

            super(ChannelCastPayload.Implementation, self).__init__(meta)
            self._torrents = torrents

        @property
        def torrents(self):
            return self._torrents


class ChannelCastRequestPayload(ChannelCastPayload):
    pass


class ChannelSearchPayload(Payload):

    """
    Propagate a search for a channel
    """
    class Implementation(Payload.Implementation):

        def __init__(self, meta, keywords):
            if __debug__:
                assert isinstance(keywords, list), 'keywords should be list'
                for keyword in keywords:
                    assert isinstance(keyword, unicode), '%s is type %s' % (keyword, type(keyword))
                    assert len(keyword) > 0

            super(ChannelSearchPayload.Implementation, self).__init__(meta)
            self._keywords = keywords

        @property
        def keywords(self):
            return self._keywords


class ChannelSearchResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, keywords, torrents):
            if __debug__:
                assert isinstance(keywords, list), 'keywords should be list'
                assert isinstance(torrents, dict), 'torrents should be a dictionary containing cid:set(infohashes)'
                for cid, infohashes in torrents.iteritems():
                    assert isinstance(cid, str)
                    assert len(cid) == 20
                    assert isinstance(infohashes, set)
                    assert not filter(lambda x: not isinstance(x, str), infohashes)
                    assert not filter(lambda x: not len(x) == 20, infohashes)
                    assert len(infohashes) > 0

            super(ChannelSearchResponsePayload.Implementation, self).__init__(meta)
            self._keywords = keywords
            self._torrents = torrents

        @property
        def keywords(self):
            return self._keywords

        @property
        def torrents(self):
            return self._torrents


class VoteCastPayload(Payload):

    """
    Propagate vote for a channel
    """
    class Implementation(Payload.Implementation):

        def __init__(self, meta, cid, vote, timestamp):
            assert isinstance(cid, str)
            assert len(cid) == 20
            assert isinstance(vote, int)
            assert vote in [-1, 0, 2]
            assert isinstance(timestamp, (int, long))

            super(VoteCastPayload.Implementation, self).__init__(meta)
            self._cid = cid
            self._vote = vote
            self._timestamp = timestamp

        @property
        def cid(self):
            return self._cid

        @property
        def vote(self):
            return self._vote

        @property
        def timestamp(self):
            return self._timestamp

class AllChannelConversion(BaseConversion):

    def __init__(self, community):
        super(AllChannelConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"channelcast"),
                                 self._encode_channelcast, self._decode_channelcast)
        self.define_meta_message(chr(2), community.get_meta_message(u"channelcast-request"),
                                 self._encode_channelcast, self._decode_channelcast)
        self.define_meta_message(chr(3), community.get_meta_message(u"channelsearch"),
                                 self._encode_channelsearch, self._decode_channelsearch)
        self.define_meta_message(chr(4), community.get_meta_message(u"channelsearch-response"),
                                 self._encode_channelsearch_response, self._decode_channelsearch_response)
        self.define_meta_message(chr(5), community.get_meta_message(u"votecast"),
                                 self._encode_votecast, self._decode_votecast)

    def _encode_channelcast(self, message):
        max_len = self._community.dispersy_sync_bloom_filter_bits / 8

        def create_msg():
            return encode(message.payload.torrents)

        packet = create_msg()
        while len(packet) > max_len:
            community = choice(message.payload.torrents.keys())
            nrTorrents = len(message.payload.torrents[community])
            if nrTorrents == 1:
                del message.payload.torrents[community]
            else:
                message.payload.torrents[community] = set(sample(message.payload.torrents[community], nrTorrents - 1))

            packet = create_msg()

        return packet,

    def _decode_channelcast(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, dict):
            raise DropPacket("Invalid payload type")

        for cid, infohashes in payload.iteritems():
            if not (isinstance(cid, str) and len(cid) == 20):
                raise DropPacket("Invalid 'cid' type or value")

            for infohash in infohashes:
                if not (isinstance(infohash, str) and len(infohash) == 20):
                    raise DropPacket("Invalid 'infohash' type or value")
        return offset, placeholder.meta.payload.implement(payload)

    def _encode_channelsearch(self, message):
        packet = encode(message.payload.keywords)
        return packet,

    def _decode_channelsearch(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, list):
            raise DropPacket("Invalid payload type")

        for keyword in payload:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")
        return offset, placeholder.meta.payload.implement(payload)

    def _encode_channelsearch_response(self, message):
        packet = encode((message.payload.keywords, message.payload.torrents))
        return packet,

    def _decode_channelsearch_response(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the channelcast-payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        keywords, torrents = payload
        for keyword in keywords:
            if not isinstance(keyword, unicode):
                raise DropPacket("Invalid 'keyword' type")

        for cid, infohashes in torrents.iteritems():
            if not (isinstance(cid, str) and len(cid) == 20):
                raise DropPacket("Invalid 'cid' type or value")

            for infohash in infohashes:
                if not (isinstance(infohash, str) and len(infohash) == 20):
                    raise DropPacket("Invalid 'infohash' type or value")

        return offset, placeholder.meta.payload.implement(keywords, torrents)

    def _encode_votecast(self, message):
        return pack('!20shl', message.payload.cid, message.payload.vote, message.payload.timestamp),

    def _decode_votecast(self, placeholder, offset, data):
        if len(data) < offset + 26:
            raise DropPacket("Unable to decode the payload")

        cid, vote, timestamp = unpack_from('!20shl', data, offset)
        if not vote in [-1, 0, 2]:
            raise DropPacket("Invalid 'vote' type or value")

        return offset + 26, placeholder.meta.payload.implement(cid, vote, timestamp)

class AllChannelCompatibility:

    """Class for providing backward compatibility for
        the AllChannel community.
    """

    def __init__(self, parent):
        self.parent = parent

    def deprecated_meta_messages(self):
        return [
            Message(self.parent, u"channelcast",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelCastPayload(),
                    self.check_channelcast,
                    self.on_channelcast),
            Message(self.parent, u"channelcast-request",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelCastRequestPayload(),
                    self.check_channelcast_request,
                    self.on_channelcast_request),
            Message(self.parent, u"channelsearch",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    ChannelSearchPayload(),
                    self.check_channelsearch,
                    self.on_channelsearch),
            Message(self.parent, u"channelsearch-response",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ChannelSearchResponsePayload(),
                    self.check_channelsearch_response,
                    self.on_channelsearch_response),
            Message(self.parent, u"votecast",
                    MemberAuthentication(),
                    PublicResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    VoteCastPayload(),
                    self.check_votecast,
                    self.on_votecast,
                    self.undo_votecast,
                    batch=BatchConfiguration(max_window=1.0))
            ]

    class Mock:
        innerdict = {}
        def put(self, field, value):
            self.innerdict[field] = value
        def __getattr__(self, name):
            if name in self.innerdict:
                return self.innerdict[name]
            else:
                raise AttributeError

    def _reconstruct_channelcast(self, message):
        mock_main = self.Mock()
        mock_torrents = []
        for community in message.payload.torrents:
            mock_torrent = self.Mock()
            mock_torrent.put('cid', community)
            mock_torrent.put('infohashes', list(message.payload.torrents[community]))
            mock_torrents.append(mock_torrent)
        mock_main.put('torrents', mock_torrents)
        return mock_main

    def _reconstruct_channelsearch(self, message):
        mock_main = self.Mock()
        mock_main.put('keywords', list(message.payload.keywords))
        return mock_main

    def _reconstruct_channelsearchresponse(self, message):
        mock_main = self.Mock()
        mock_torrents = []
        for community in message.payload.torrents:
            mock_torrent = self.Mock()
            mock_torrent.put('cid', community)
            mock_torrent.put('infohashes', list(message.payload.torrents[community]))
            mock_torrents.append(mock_torrent)
        mock_main.put('torrents', mock_torrents)
        mock_main.put('keywords', list(message.payload.keywords))
        return mock_main

    def _reconstruct_votecast(self, message):
        mock_main = self.Mock()
        mock_main.put('cid', message.payload.cid)
        mock_main.put('vote', message.payload.vote)
        mock_main.put('timestamp', message.payload.timestamp)
        return mock_main

    def check_channelcast(self, messages):
        for message in messages:
            out = self.parent.check_channelcast(message, self._reconstruct_channelcast(message)).next()
            yield out

    def on_channelcast(self, messages):
        for message in messages:
            self.parent.on_channelcast(message, self._reconstruct_channelcast(message))

    def check_channelcast_request(self, messages):
        for message in messages:
            yield message

    def on_channelcast_request(self, messages):
        for message in messages:
            self.parent.on_channelcastrequest(message, self._reconstruct_channelcast(message))

    def check_channelsearch(self, messages):
        for message in messages:
            yield message

    def on_channelsearch(self, messages):
        for message in messages:
            self.parent.on_channelsearch(message, self._reconstruct_channelsearch(message))

    def check_channelsearch_response(self, messages):
        for message in messages:
            out = self.parent.check_channelsearchresponse(message,
                                                          self._reconstruct_channelsearchresponse(message)).next()
            yield out

    def on_channelsearch_response(self, messages):
        for message in messages:
            self.parent.on_channelsearchresponse(message, self._reconstruct_channelsearchresponse(message))

    def check_votecast(self, messages):
        for message in messages:
            out = self.parent.check_votecast(message, self._reconstruct_votecast(message)).next()
            yield out

    def on_votecast(self, messages):
        for message in messages:
            self.parent.on_votecast(message, self._reconstruct_votecast(message))

    def undo_votecast(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            message = packet.load_message()
            self.parent.undo_votecast(message, self._reconstruct_votecast(message), redo)

