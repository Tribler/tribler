from Tribler.Core.dispersy.payload import Payload

class PropagateTorrentsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohashes):
            assert isinstance(infohashes, (tuple, list))
            assert not filter(lambda x: not isinstance(x, str), infohashes)
            assert not filter(lambda x: not len(x) == 20, infohashes)
            super(PropagateTorrentsPayload.Implementation, self).__init__(meta)
            self._infohashes = infohashes

        @property
        def infohashes(self):
            return self._infohashes

class TorrentRequestPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohash):
            assert isinstance(infohash, str)
            assert len(infohash) == 20
            super(TorrentRequestPayload.Implementation, self).__init__(meta)
            self._infohash = infohash

        @property
        def infohash(self):
            return self._infohash

