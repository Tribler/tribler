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
                    assert isinstance(keyword, str)
                    assert len(keyword) > 0
            
            super(ChannelSearchPayload.Implementation, self).__init__(meta)
            self._keywords = keywords

        @property
        def keywords(self):
            return self._keywords
        
class ChannelSearchResponsePayload(ChannelCastPayload):
    pass
        
class VoteCastPayload(Payload):
    """
    Propagate vote for a channel
    """
    class Implementation(Payload.Implementation):
        def __init__(self, meta, cid, vote, timestamp):
            assert isinstance(cid, str)
            assert len(cid) == 20
            assert isinstance(vote, int)
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