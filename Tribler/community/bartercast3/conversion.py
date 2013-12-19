from struct import pack, unpack_from

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket


class BarterConversion(BinaryConversion):

    def __init__(self, community):
        super(BarterConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"barter-record"), self._encode_barter_record, self._decode_barter_record)

    def _encode_barter_record(self, message):
        payload = message.payload

        return (pack(">QQ",
                     long(payload.upload_first_to_second),
                     long(payload.upload_second_to_first),
                # the following parameters are used for debugging only
                pack(">LQQQQLQQQQ",
                     long(payload.first_timestamp),
                     long(payload.first_upload),
                     long(payload.first_download),
                     long(payload.first_total_up),
                     long(payload.first_total_down),
                     long(payload.second_timestamp),
                     long(payload.second_upload),
                     long(payload.second_download),
                     long(payload.second_total_up),
                     long(payload.second_total_down))))

    def _decode_barter_record(self, placeholder, offset, data):
        if len(data) < offset + 88:
            raise DropPacket("Insufficient packet size (_decode_barter_record)")

        (upload_first_to_second,
         upload_second_to_first,
         # the following parameters are used for debugging only
         first_timestamp,
         first_upload,
         first_download,
         first_total_up,
         first_total_down,
         second_timestamp,
         second_upload,
         second_download,
         second_total_up,
         second_total_down) = unpack_from(">QQLQQQQLQQQQ", data, offset)
        offset += 88

        return offset, placeholder.meta.payload.implement(upload_first_to_second,
                                                          upload_second_to_first,
                                                          # the following parameters are used for debugging only
                                                          float(first_timestamp),
                                                          first_upload,
                                                          first_download,
                                                          first_total_up,
                                                          first_total_down,
                                                          float(second_timestamp),
                                                          second_upload,
                                                          second_download,
                                                          second_total_up,
                                                          second_total_down)
