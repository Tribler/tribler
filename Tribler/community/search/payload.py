from Tribler.dispersy.payload import Payload, IntroductionRequestPayload
from Tribler.dispersy.bloomfilter import BloomFilter


class TasteIntroPayload(IntroductionRequestPayload):

    class Implementation(IntroductionRequestPayload.Implementation):

        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier, num_preferences=0, taste_bloom_filter=None):
            IntroductionRequestPayload.Implementation.__init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)

            self._num_preferences = num_preferences
            self._taste_bloom_filter = taste_bloom_filter

        def set_num_preferences(self, num_preferences):
            self._num_preferences = num_preferences

        def set_taste_bloom_filter(self, taste_bloom_filter):
            self._taste_bloom_filter = taste_bloom_filter

        @property
        def num_preferences(self):
            return self._num_preferences

        @property
        def taste_bloom_filter(self):
            return self._taste_bloom_filter


class SearchRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, keywords, bloom_filter=None):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(keywords, list), 'keywords should be list'
                for keyword in keywords:
                    assert isinstance(keyword, unicode), '%s is type %s' % (keyword, type(keyword))
                    assert len(keyword) > 0

                assert not bloom_filter or isinstance(bloom_filter, BloomFilter), type(bloom_filter)

            super(SearchRequestPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._keywords = keywords
            self._bloom_filter = bloom_filter

        @property
        def identifier(self):
            return self._identifier

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
                    assert len(result) > 8

                    infohash, swarmname, length, nrfiles, category_list, creation_date, seeders, leechers, cid = result[:9]
                    assert isinstance(infohash, str), type(infohash)
                    assert len(infohash) == 20
                    assert isinstance(swarmname, unicode), type(swarmname)
                    assert isinstance(length, long), type(length)
                    assert isinstance(nrfiles, int), type(nrfiles)
                    assert isinstance(category_list, list), type(category_list)
                    assert all(isinstance(key, unicode) for key in category_list), category_list
                    assert isinstance(creation_date, long), type(creation_date)
                    assert isinstance(seeders, int), type(seeders)
                    assert isinstance(leechers, int), type(leechers)
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


class TorrentCollectRequestPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, identifier, hashtype, torrents):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(torrents, list), type(torrents)
                for infohash, seeders, leechers, ago in torrents:
                    assert isinstance(infohash, str)
                    assert len(infohash) == 20, "%d, %s" % (len(infohash), infohash)
                    assert isinstance(seeders, int), type(seeders)
                    assert 0 <= seeders < 2 ** 16, seeders
                    assert isinstance(leechers, int), type(leechers)
                    assert 0 <= leechers < 2 ** 16, leechers
                    assert isinstance(ago, int), type(ago)
                    assert 0 <= ago < 2 ** 16, ago

                assert isinstance(hashtype, int), type(hashtype)
                assert 0 <= hashtype < 2 ** 16, hashtype

            super(TorrentCollectRequestPayload.Implementation, self).__init__(meta)

            self._identifier = identifier
            self._hashtype = hashtype
            self._torrents = torrents

        @property
        def identifier(self):
            return self._identifier

        @property
        def hashtype(self):
            return self._hashtype

        @property
        def torrents(self):
            return self._torrents


class TorrentCollectResponsePayload(TorrentCollectRequestPayload):
    pass
