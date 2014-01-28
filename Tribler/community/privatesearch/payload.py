from Tribler.dispersy.payload import Payload, IntroductionRequestPayload
from Tribler.dispersy.bloomfilter import BloomFilter

MAXLONG128 = (1 << 1024) - 1
MAXLONG256 = (1 << 2048) - 1

# Search stuffs
class SearchRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, ttl, keywords, bloom_filter=None):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(ttl, int), type(ttl)
                assert isinstance(keywords, list), 'keywords should be list'
                for keyword in keywords:
                    assert isinstance(keyword, unicode), '%s is type %s' % (keyword, type(keyword))
                    assert len(keyword) > 0

                assert not bloom_filter or isinstance(bloom_filter, BloomFilter), type(bloom_filter)

            super(SearchRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._ttl = ttl
            self._keywords = keywords
            self._bloom_filter = bloom_filter

        @property
        def identifier(self):
            return self._identifier

        @property
        def ttl(self):
            return self._ttl

        @property
        def keywords(self):
            return self._keywords

        @property
        def bloom_filter(self):
            return self._bloom_filter


class SearchResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, results):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(results, list), type(results)
                for result in results:
                    assert isinstance(result, tuple), type(result)
                    assert len(result) > 10

                    infohash, swarmname, length, nrfiles, categorykeys, creation_date, seeders, leechers, swift_hash, swift_torrent_hash, cid = result[:11]
                    assert isinstance(infohash, str), type(infohash)
                    assert len(infohash) == 20, len(infohash)
                    assert isinstance(swarmname, unicode), type(swarmname)
                    assert isinstance(length, long), type(length)
                    assert isinstance(nrfiles, int), type(nrfiles)
                    assert isinstance(categorykeys, list), type(categorykeys)
                    assert all(isinstance(key, unicode) for key in categorykeys), categorykeys
                    assert isinstance(creation_date, long), type(creation_date)
                    assert isinstance(seeders, int), type(seeders)
                    assert isinstance(leechers, int), type(leechers)
                    assert not swift_hash or isinstance(swift_hash, str), type(swift_hash)
                    assert not swift_hash or len(swift_hash) == 20, swift_hash
                    assert not swift_torrent_hash or isinstance(swift_torrent_hash, str), type(swift_torrent_hash)
                    assert not swift_torrent_hash or len(swift_torrent_hash) == 20, swift_torrent_hash
                    assert not cid or isinstance(cid, str), type(cid)
                    assert not cid or len(cid) == 20, cid

            super(SearchResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._results = results

        @property
        def identifier(self):
            return self._identifier

        @property
        def results(self):
            return self._results


class TorrentRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, torrents):
            if __debug__:
                assert isinstance(torrents, dict), type(torrents)
                for cid, infohashes in torrents.iteritems():
                    assert isinstance(cid, str)
                    assert len(cid) == 20
                    assert isinstance(infohashes, set)
                    assert not filter(lambda x: not isinstance(x, str), infohashes)
                    assert not filter(lambda x: not len(x) == 20, infohashes)
                    assert len(infohashes) > 0

            super(TorrentRequestPayload.Implementation, self).__init__(meta)
            self._torrents = torrents

        @property
        def torrents(self):
            return self._torrents


class TorrentPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, timestamp, name, files, trackers):
            assert isinstance(infohash, str), 'infohash is a %s' % type(infohash)
            assert len(infohash) == 20, 'infohash has length %d' % len(infohash)
            assert isinstance(timestamp, (int, long))

            assert isinstance(name, unicode)
            assert isinstance(files, tuple)
            for path, length in files:
                assert isinstance(path, unicode)
                assert isinstance(length, (int, long))

            assert isinstance(trackers, tuple)
            for tracker in trackers:
                assert isinstance(tracker, str), 'tracker is a %s' % type(tracker)

            super(TorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._timestamp = timestamp
            self._name = name
            self._files = files
            self._trackers = trackers

        @property
        def infohash(self):
            return self._infohash

        @property
        def timestamp(self):
            return self._timestamp

        @property
        def name(self):
            return self._name

        @property
        def files(self):
            return self._files

        @property
        def trackers(self):
            return self._trackers
