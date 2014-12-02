from Tribler.dispersy.payload import Payload


class MetadataPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, data_list, prev_mid=None, prev_global_time=None):
            assert isinstance(infohash, str), u"infohash is a %s" % type(infohash)
            assert len(infohash) == 20, u"infohash has length %d" % len(infohash)

            assert isinstance(data_list, list), u"data_list is a %s" % type(data_list)
            for data in data_list:
                assert isinstance(data, tuple), u"data is a %s" % type(data)
                assert len(data) == 2, u"data has length %d" % len(data)

            assert not prev_mid or isinstance(prev_mid, str), u"prev_mid is a %s" % type(prev_mid)
            assert not prev_mid or len(prev_mid) == 20, u"prev_mid has length %d" % len(prev_mid)
            assert not prev_global_time or isinstance(prev_global_time, (int, long)), \
                u"prev_global_time is a %s" % type(prev_global_time)

            super(MetadataPayload.Implementation, self).__init__(meta)

            self._infohash = infohash
            self._data_list = data_list

            self._prev_mid = prev_mid
            self._prev_global_time = prev_global_time

        @property
        def infohash(self):
            return self._infohash

        @property
        def data_list(self):
            return self._data_list

        @property
        def prev_mid(self):
            return self._prev_mid

        @property
        def prev_global_time(self):
            return self._prev_global_time
