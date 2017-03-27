from Tribler.dispersy.payload import Payload


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
