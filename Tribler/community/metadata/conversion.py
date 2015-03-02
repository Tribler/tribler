import zlib
from random import sample

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket

from Tribler.Core.Utilities.encoding import encode, decode


class MetadataConversion(BinaryConversion):

    def __init__(self, community):
        super(MetadataConversion, self).__init__(community, "\x02")
        self.define_meta_message(chr(1), community.get_meta_message(u"metadata"),
                                 self._encode_metadata,
                                 self._decode_metadata)

    def _encode_metadata(self, message):
        """
        Encodes the metadata message payload.
        """
        max_len = 8 * 1024

        data_list = message.payload.data_list

        def create_msg():
            msg_dict = {
                "infohash": message.payload.infohash,
                "data-list": message.payload.data_list
            }
            if message.payload.prev_mid:
                msg_dict["prev-mid"] = message.payload.prev_mid
                msg_dict["prev-global-time"] = message.payload.prev_global_time

            normal_msg = encode(msg_dict)
            return zlib.compress(normal_msg)

        compressed_msg = create_msg()
        while len(compressed_msg) > max_len:
            # reduce files by the amount we are currently to big
            reduce_by = max_len / (len(compressed_msg) * 1.0)
            nr_data_to_include = int(len(data_list) * reduce_by)
            data_list = sample(data_list, nr_data_to_include)

            compressed_msg = create_msg()
        return compressed_msg,

    def _decode_metadata(self, placeholder, offset, data):
        """
        Decodes the metadata message payload.
        """
        uncompressed_data = zlib.decompress(data[offset:])
        offset = len(data)

        try:
            _, dic = decode(uncompressed_data)
        except ValueError:
            raise DropPacket("Unable to decode metadata message payload")

        if not "infohash" in dic:
            raise DropPacket("Missing 'infohash'")
        infohash = dic["infohash"]
        if not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket("Invalid 'infohash' type or value")

        if not "data-list" in dic:
            raise DropPacket("Missing 'data-list'")
        data_list = dic["data-list"]
        if not isinstance(data_list, list):
            raise DropPacket("Invalid 'data-list' type or value")
        for data in data_list:
            if not isinstance(data, tuple):
                raise DropPacket("Invalid 'data' type")
            elif len(data) != 2:
                raise DropPacket("Invalid 'data' value")
            elif len(data[1]) > 1024:
                raise DropPacket("'data' value too big (> 1024 bytes)")

        prev_mid = dic.get("prev-mid", None)
        if prev_mid and not (isinstance(prev_mid, str) and len(prev_mid) == 20):
            raise DropPacket("Invalid 'prev-mid' type or value")

        prev_global_time = dic.get("prev-global-time", None)
        if prev_global_time and not isinstance(prev_global_time, (int, long)):
            raise DropPacket("Invalid 'prev-global-time' type")

        if prev_mid and not prev_global_time:
            raise DropPacket("Incomplete previous pointer (mid and NO global-time)")
        if not prev_mid and prev_global_time:
            raise DropPacket("Incomplete previous pointer (global-time and NO mid)")

        return offset, placeholder.meta.payload.implement(infohash, data_list, prev_mid, prev_global_time)
