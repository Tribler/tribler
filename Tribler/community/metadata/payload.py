from Tribler.dispersy.message import Packet
from Tribler.dispersy.payload import Payload
from struct import pack


class MetadataPayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, infohash, roothash, data_list, prev_metadata_mid=None, prev_metadata_global_time=None):
            assert isinstance(infohash, str), u"infohash is a %s" % type(infohash)
            assert len(infohash) == 20, u"infohash has length %d" % len(infohash)
            if roothash:
                assert isinstance(roothash, str), u"roothash is a %s" % type(roothash)
                assert len(roothash) == 20, u"roothash has length %d" % len(roothash)

            assert isinstance(data_list, list), u"data_list is a %s" % type(data_list)
            for data in data_list:
                assert isinstance(data, tuple), u"data is a %s" % type(data)
                assert len(data) == 2, u"data has length %d" % len(data)

            assert not prev_metadata_mid or isinstance(prev_metadata_mid, str), u"prev_metadata_mid is a %s" % type(prev_metadata_mid)
            assert not prev_metadata_mid or len(prev_metadata_mid) == 20, u"prev_metadata_mid has length %d" % len(prev_metadata_mid)
            assert not prev_metadata_global_time or isinstance(prev_metadata_global_time, (int, long)), u"prev_metadata_global_time is a %s" % type(prev_metadata_global_time)

            super(MetadataPayload.Implementation, self).__init__(meta)

            self._infohash = infohash
            self._roothash = roothash
            self._data_list = data_list

            self._prev_metadata_mid = prev_metadata_mid
            self._prev_metadata_global_time = prev_metadata_global_time

        @property
        def infohash(self):
            return self._infohash

        @property
        def roothash(self):
            return self._roothash

        @property
        def data_list(self):
            return self._data_list

        @property
        def prev_metadata_mid(self):
            return self._prev_metadata_mid

        @property
        def prev_metadata_global_time(self):
            return self._prev_metadata_global_time
