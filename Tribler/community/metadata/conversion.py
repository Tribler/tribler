from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket, Packet,\
    DelayPacketByMissingMessage, DelayPacketByMissingMember

from Tribler.Core.Utilities.encoding import encode, decode


class MetadataConversion(BinaryConversion):

    def __init__(self, community):
        super(MetadataConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"metadata"), self._encode_metadata, self._decode_metadata)


    def _encode_metadata(self, message):
        """
        Encodes the metadata message payload.
        """
        dict = {u"infohash" : message.payload.infohash,
                u"roothash": message.payload.roothash,
                u"data-list" : message.payload.data_list,
                u"this-metadata-mid": message.authentication.member.mid,
                u"this-metadata-global-time": message.distribution.global_time
        }

        if message.payload.prev_metadata_mid:
            dict[u"prev-metadata-mid"] = message.payload.prev_metadata_mid
            dict[u"prev-metadata-global-time"] = message.payload.prev_metadata_global_time

        return encode(dict),


    def _decode_metadata(self, placeholder, offset, data):
        """
        Decodes the metadata message payload.
        """
        try:
            offset, dic = decode(data, offset)
        except ValueError:
            raise DropPacket(u"Unable to decode metadata message payload")

        if not u"infohash" in dic:
            raise DropPacket(u"Missing 'infohash'")
        infohash = dic[u"infohash"]
        if not (isinstance(infohash, str) and len(infohash) == 20):
            raise DropPacket(u"Invalid 'infohash' type or value")

        if not u"roothash" in dic:
            raise DropPacket(u"Missing 'roothash'")
        roothash = dic[u"roothash"]
        if not roothash or not (isinstance(roothash, str) and len(roothash) == 20):
            raise DropPacket(u"Invalid 'roothash' type or value")

        if not u"data-list" in dic:
            raise DropPacket(u"Missing 'data-list'")
        data_list = dic[u"data-list"]
        if not isinstance(data_list, list):
            raise DropPacket(u"Invalid 'data-list' type or value")
        for data in data_list:
            if not isinstance(data, tuple):
                raise DropPacket(u"Invalid 'data' type")
            elif len(data) != 2:
                raise DropPacket(u"Invalid 'data' value")

        prev_metadata_mid = dic.get(u"prev-metadata-mid", None)
        if prev_metadata_mid and not (isinstance(prev_metadata_mid, str) and len(prev_metadata_mid) == 20):
            raise DropPacket(u"Invalid 'prev-metadata-mid' type or value")

        prev_metadata_global_time = dic.get(u"prev-metadata-global-time", None)
        if prev_metadata_global_time and not isinstance(prev_metadata_global_time, (int, long)):
            raise DropPacket(u"Invalid 'prev-metadata-global-time' type")

        return offset, placeholder.meta.payload.implement(infohash, roothash, data_list, prev_metadata_mid, prev_metadata_global_time)
