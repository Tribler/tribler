from struct import pack, unpack_from
from random import choice, sample
from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.bloomfilter import BloomFilter

from binascii import hexlify, unhexlify
def long_to_bytes(val, nrbytes):
    hex_val = '%x' % abs(val)
    padding = '0' * ((abs(nrbytes) * 2) - len(hex_val))
    result = unhexlify(padding + hex_val)[::-1]

    if nrbytes < 0:
        return ("-" if val < 0 else "+") + result
    return result

def bytes_to_long(val):
    if val[0] == "-" or val[0] == "+":
        _val = long(hexlify(val[1:][::-1]), 16)
        if val[0] == "-":
            return -_val
        return _val
    else:
        return long(hexlify(val[::-1]), 16)

class SemanticConversion(BinaryConversion):
    def __init__(self, community):
        super(SemanticConversion, self).__init__(community, "\x01")
        # we need to use 4 and 5 as we are combining this overlay with the searchcommunity which has 1,2,and 3 defined.
        self.define_meta_message(chr(4), community.get_meta_message(u"ping"), lambda message: self._encode_decode(self._encode_ping, self._decode_ping, message), self._decode_ping)
        self.define_meta_message(chr(5), community.get_meta_message(u"pong"), lambda message: self._encode_decode(self._encode_pong, self._decode_pong, message), self._decode_pong)

    def _encode_ping(self, message):
        hashpack = '20s20sHHH' * len(message.payload.torrents)
        torrents = [item for sublist in message.payload.torrents for item in sublist]
        return pack('!H' + hashpack, message.payload.identifier, *torrents),

    def _decode_ping(self, placeholder, offset, data):
        if len(data) < offset + 2:
            raise DropPacket("Insufficient packet size")

        identifier, = unpack_from('!H', data, offset)
        offset += 2

        length = len(data) - offset
        if length % 46 != 0:
            raise DropPacket("Invalid number of bytes available")

        if length:
            hashpack = '20s20sHHH' * (length / 46)
            hashes = unpack_from('!' + hashpack, data, offset)
            offset += length

            torrents = []
            for i in range(0, len(hashes), 5):
                torrents.append([hashes[i], hashes[i + 1], hashes[i + 2], hashes[i + 3], hashes[i + 4]])
        else:
            torrents = []

        return offset, placeholder.meta.payload.implement(identifier, torrents)

    def _encode_pong(self, message):
        return self._encode_ping(message)
    def _decode_pong(self, placeholder, offset, data):
        return self._decode_ping(placeholder, offset, data)

    def _encode_decode(self, encode, decode, message):
        result = encode(message)
        try:
            decode(None, 0, result[0])

        except DropPacket:
            raise
        except:
            pass
        return result

class ForwardConversion(SemanticConversion):

    def _encode_introduction_request(self, message):
        data = BinaryConversion._encode_introduction_request(self, message)

        if message.payload.introduce_me_to:
            data.append(pack('!20s', message.payload.introduce_me_to))
        return data

    def _decode_introduction_request(self, placeholder, offset, data):
        offset, payload = BinaryConversion._decode_introduction_request(self, placeholder, offset, data)

        # if there's still bytes in this request, treat them as taste_bloom_filter
        has_stuff = len(data) > offset
        if has_stuff:
            length = len(data) - offset
            if length != 20:
                raise DropPacket("Invalid number of bytes available (ir)")

            candidate_mid, = unpack_from('!20s', data, offset)
            payload.set_introduce_me_to(candidate_mid)

            offset += length
        return offset, payload

class PSearchConversion(ForwardConversion):

    def __init__(self, community):
        ForwardConversion.__init__(self, community)
        self.define_meta_message(chr(6), community.get_meta_message(u"msimilarity-request"), lambda message: self._encode_decode(self._encode_sum_request, self._decode_sum_request, message), self._decode_sum_request)
        self.define_meta_message(chr(7), community.get_meta_message(u"similarity-request"), lambda message: self._encode_decode(self._encode_sum_request, self._decode_sum_request, message), self._decode_sum_request)
        self.define_meta_message(chr(8), community.get_meta_message(u"msimilarity-response"), lambda message: self._encode_decode(self._encode_sums, self._decode_sums, message), self._decode_sums)
        self.define_meta_message(chr(9), community.get_meta_message(u"similarity-response"), lambda message: self._encode_decode(self._encode_sum, self._decode_sum, message), self._decode_sum)

    def _encode_sum_request(self, message):
        str_n = long_to_bytes(message.payload.key_n, 128)
        str_prefs = [long_to_bytes(preference, 256) for preference in message.payload.preference_list]
        str_prefs = str_prefs + [long_to_bytes(preference, 256) for preference in message.payload.global_vector]

        fmt = "!H128s" + "256s"*len(str_prefs)
        packet = pack(fmt, message.payload.identifier, str_n, *str_prefs)
        return packet,

    def _decode_sum_request(self, placeholder, offset, data):
        identifier, str_n = unpack_from('!H128s', data, offset)
        offset += 130

        length = len(data) - offset
        if length % 256 != 0:
            raise DropPacket("Invalid number of bytes available (encr_res)")

        if length:
            hashpack = '256s' * (length / 256)
            str_prefs = unpack_from('!' + hashpack, data, offset)

            prefs = [bytes_to_long(str_pref) for str_pref in str_prefs]
            global_vector = prefs[len(prefs) / 2:]
            prefs = prefs[:len(prefs) / 2]
            offset += length

        return offset, placeholder.meta.payload.implement(identifier, bytes_to_long(str_n), prefs, global_vector)

    def _encode_sum(self, message):
        str_sum = long_to_bytes(message.payload._sum, 256)
        return pack("!H256s", message.payload.identifier, str_sum),

    def _decode_sum(self, placeholder, offset, data):
        identifier, _sum = unpack_from('!H256s', data, offset)
        offset += 258

        return offset, placeholder.meta.payload.implement(identifier, bytes_to_long(_sum))

    def _encode_sums(self, message):
        str_sum = long_to_bytes(message.payload._sum, 256)

        sums = []
        for candidate_mid, address_sum in message.payload.sums:
            sums.append(candidate_mid)
            sums.append(long_to_bytes(address_sum, 256))

        fmt = "!H256s" + "20s256s" * len(message.payload.sums)
        packet = pack(fmt, message.payload.identifier, str_sum, *sums)
        return packet,

    def _decode_sums(self, placeholder, offset, data):
        identifier, _sum = unpack_from('!H256s', data, offset)
        offset += 258

        length = len(data) - offset
        if length % 276 != 0:
            raise DropPacket("Invalid number of bytes available (encr_sums)")

        _sums = []
        if length:
            hashpack = '20s256s' * (length / 276)
            raw_values = unpack_from('!' + hashpack, data, offset)
            for i in range(len(raw_values) / 2):
                candidate_mid = raw_values[i * 2]
                _sums.append([candidate_mid, bytes_to_long(raw_values[(i * 2) + 1])])

            offset += length

        return offset, placeholder.meta.payload.implement(identifier, bytes_to_long(_sum), _sums)

class HSearchConversion(ForwardConversion):

    def __init__(self, community):
        ForwardConversion.__init__(self, community)
        self.define_meta_message(chr(6), community.get_meta_message(u"msimilarity-request"), lambda message: self._encode_decode(self._encode_simi_request, self._decode_simi_request, message), self._decode_simi_request)
        self.define_meta_message(chr(7), community.get_meta_message(u"similarity-request"), lambda message: self._encode_decode(self._encode_simi_request, self._decode_simi_request, message), self._decode_simi_request)
        self.define_meta_message(chr(8), community.get_meta_message(u"msimilarity-response"), lambda message: self._encode_decode(self._encode_simi_responses, self._decode_simi_responses, message), self._decode_simi_responses)
        self.define_meta_message(chr(9), community.get_meta_message(u"similarity-response"), lambda message: self._encode_decode(self._encode_simi_response, self._decode_simi_response, message), self._decode_simi_response)

    def _encode_simi_request(self, message):
        str_n = long_to_bytes(message.payload.key_n, 128)
        str_prefs = [long_to_bytes(preference, 128) for preference in message.payload.preference_list]

        fmt = "!H128s" + "128s"*len(str_prefs)
        packet = pack(fmt, message.payload.identifier, str_n, *str_prefs)
        return packet,

    def _decode_simi_request(self, placeholder, offset, data):
        identifier, str_n = unpack_from('!H128s', data, offset)
        offset += 130

        length = len(data) - offset
        if length % 128 != 0:
            raise DropPacket("Invalid number of bytes available (simi_request)")

        if length:
            hashpack = '128s' * (length / 128)
            str_prefs = unpack_from('!' + hashpack, data, offset)
            prefs = [bytes_to_long(str_pref) for str_pref in str_prefs]
            offset += length
        else:
            prefs = []

        return offset, placeholder.meta.payload.implement(identifier, bytes_to_long(str_n), prefs)

    def _encode_simi_response(self, message):
        str_identifer = pack("!H", message.payload.identifier)
        str_prefs = pack("!" + "128s"*len(message.payload.preference_list), *[long_to_bytes(preference, 128) for preference in message.payload.preference_list])
        str_his_prefs = pack("!" + "20s"*len(message.payload.his_preference_list), *message.payload.his_preference_list)
        return encode([str_identifer, str_prefs, str_his_prefs]),

    def _decode_simi_response(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the simi_res-payload")

        str_identifier, str_prefs, str_his_prefs = payload

        identifier, = unpack_from('!H', str_identifier)

        length = len(str_prefs)
        if length % 128 != 0:
            raise DropPacket("Invalid number of bytes available (simi_res)")
        if length:
            hashpack = '128s' * (length / 128)
            hashes = unpack_from('!' + hashpack, str_prefs)
            hashes = [bytes_to_long(hash) for hash in hashes]
        else:
            hashes = []

        length = len(str_his_prefs)
        if length % 20 != 0:
            raise DropPacket("Invalid number of bytes available (simi_res)")
        if length:
            hashpack = '20s' * (length / 20)
            his_hashes = unpack_from('!' + hashpack, str_his_prefs)
        else:
            his_hashes = []
        return offset, placeholder.meta.payload.implement(identifier, hashes, his_hashes)

    def _encode_simi_responses(self, message):
        def _encode_response(mid, preference_list, his_preference_list):
            str_mid = pack("!20s", mid) if mid else ''
            str_prefs = pack("!" + "128s"*len(preference_list), *[long_to_bytes(preference, 128) for preference in preference_list])
            str_hprefs = pack("!" + "20s"*len(his_preference_list), *his_preference_list)
            return (str_mid, str_prefs, str_hprefs)

        responses = []
        responses.append(_encode_response(None, message.payload.preference_list, message.payload.his_preference_list))
        for mid, list_tuple in message.payload.bundled_responses:
            responses.append(_encode_response(mid, list_tuple[0], list_tuple[1]))

        packet = pack('!H', message.payload.identifier), responses
        return encode(packet),

    def _decode_simi_responses(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the simi-payload")

        identifier, responses = payload[:2]

        if len(identifier) != 2:
            raise DropPacket("Unable to decode the search-response-payload, got %d bytes expected 2" % (len(identifier)))
        identifier, = unpack_from('!H', identifier)

        prefs = hprefs = None
        bundled_responses = []
        for str_mid, str_prefs, str_hprefs in responses:
            length = len(str_prefs)
            if length % 128 != 0:
                raise DropPacket("Invalid number of bytes available (encr_res)")
            if length:
                hashpack = '128s' * (length / 128)
                hashes = unpack_from('!' + hashpack, str_prefs)
                hashes = [bytes_to_long(hash) for hash in hashes]

            length = len(str_hprefs)
            if length % 20 != 0:
                raise DropPacket("Invalid number of bytes available (encr_res)")
            if length:
                hashpack = '20s' * (length / 20)
                his_hashes = list(unpack_from('!' + hashpack, str_hprefs))
            else:
                his_hashes = []

            if str_mid:
                str_mid, = unpack_from("!20s", str_mid)
                bundled_responses.append((str_mid, (hashes, his_hashes)))
            else:
                prefs = hashes
                hprefs = his_hashes

        return offset, placeholder.meta.payload.implement(identifier, [prefs, hprefs], bundled_responses)

class PoliSearchConversion(ForwardConversion):

    def __init__(self, community):
        ForwardConversion.__init__(self, community)
        self.define_meta_message(chr(6), community.get_meta_message(u"msimilarity-request"), lambda message: self._encode_decode(self._encode_simi_request, self._decode_simi_request, message), self._decode_simi_request)
        self.define_meta_message(chr(7), community.get_meta_message(u"similarity-request"), lambda message: self._encode_decode(self._encode_simi_request, self._decode_simi_request, message), self._decode_simi_request)
        self.define_meta_message(chr(8), community.get_meta_message(u"msimilarity-response"), lambda message: self._encode_decode(self._encode_simi_responses, self._decode_simi_responses, message), self._decode_simi_responses)
        self.define_meta_message(chr(9), community.get_meta_message(u"similarity-response"), lambda message: self._encode_decode(self._encode_simi_response, self._decode_simi_response, message), self._decode_simi_response)

    def _encode_simi_request(self, message):
        contents = []

        fmt = "!H128s"
        contents.append(long_to_bytes(message.payload.key_n, 128))

        if len(message.payload.coefficients) > 0:
            fmt += "257s"
            contents.append(long_to_bytes(message.payload.coefficients.values()[0][0], -256))

        for partition, coeffs in message.payload.coefficients.iteritems():
            fmt += "BB" + "257s"*(len(coeffs) - 1)
            contents.append(partition)
            contents.append(len(coeffs) - 1)
            contents.extend([long_to_bytes(coeff, -256) for coeff in coeffs[1:]])

        packet = pack(fmt, message.payload.identifier, *contents)
        return packet,

    def _decode_simi_request(self, placeholder, offset, data):
        identifier, str_n = unpack_from('!H128s', data, offset)
        offset += 130

        preferences = {}
        length = len(data) - offset
        if length:
            one_coeff, = unpack_from("!257s", data, offset)
            one_coeff = bytes_to_long(one_coeff)

            offset += 257
            length = len(data) - offset

        while length:
            partition, nr_coeffs = unpack_from("!BB", data, offset)
            offset += 2

            hashpack = '257s' * nr_coeffs
            str_coeffs = unpack_from('!' + hashpack, data, offset)
            offset += 257 * nr_coeffs
            preferences[partition] = [one_coeff] + [bytes_to_long(str_coeff) for str_coeff in str_coeffs]

            length = len(data) - offset
        return offset, placeholder.meta.payload.implement(identifier, bytes_to_long(str_n), preferences)

    def _encode_simi_response(self, message):
        str_identifer = pack("!H", message.payload.identifier)
        str_prefs = pack("!" + "256s"*len(message.payload.my_response), *[long_to_bytes(preference, 256) for preference in message.payload.my_response])
        return encode([str_identifer, str_prefs]),

    def _decode_simi_response(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the encr-payload")

        str_identifier, str_prefs = payload

        identifier, = unpack_from('!H', str_identifier)

        length = len(str_prefs)
        if length % 256 != 0:
            raise DropPacket("Invalid number of bytes available (encr_res)")

        if length:
            hashpack = '256s' * (length / 256)
            hashes = unpack_from('!' + hashpack, str_prefs)
            hashes = [bytes_to_long(hash) for hash in hashes]
        else:
            hashes = []

        return offset, placeholder.meta.payload.implement(identifier, hashes)

    def _encode_simi_responses(self, message):
        max_len = 65000 - (1500 - (self._community.dispersy_sync_bloom_filter_bits / 8))

        def create_msg():
            def _encode_response(mid, evaluated_polinomials):
                str_mid = pack("!20s", mid) if mid else ''
                str_polynomials = pack("!" + "256s"*len(evaluated_polinomials), *[long_to_bytes(py, 256) for py in evaluated_polinomials])
                return (str_mid, str_polynomials)

            responses = []
            responses.append(_encode_response(None, message.payload.my_response))
            for mid, response in message.payload.bundled_responses:
                responses.append(_encode_response(mid, response))

            packet = pack('!H', message.payload.identifier), responses
            return encode(packet)

        packet = create_msg()
        while len(packet) > max_len:
            nr_to_reduce = int((len(packet) - max_len) / 256.0) + 1

            for _ in range(nr_to_reduce):
                index = choice(range(len(message.payload.bundled_responses)))
                nr_polynomials = len(message.payload.bundled_responses[index][1])
                if nr_polynomials <= 1:
                    message.payload.bundled_responses.pop(index)
                else:
                    message.payload.bundled_responses[index] = (message.payload.bundled_responses[index][0], sample(message.payload.bundled_responses[index][1], nr_polynomials - 1))
            packet = create_msg()

        return packet,

    def _decode_simi_responses(self, placeholder, offset, data):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the simi-payload")

        identifier, responses = payload[:2]

        if len(identifier) != 2:
            raise DropPacket("Unable to decode the search-response-payload, got %d bytes expected 2" % (len(identifier)))
        identifier, = unpack_from('!H', identifier)

        prefs = None
        bundled_responses = []
        for str_mid, str_prefs in responses:
            length = len(str_prefs)
            if length % 256 != 0:
                raise DropPacket("Invalid number of bytes available (encr_res)")

            if length:
                hashpack = '256s' * (length / 256)
                hashes = unpack_from('!' + hashpack, str_prefs)
                hashes = [bytes_to_long(hash) for hash in hashes]
            else:
                hashes = []

            if str_mid:
                str_mid, = unpack_from("!20s", str_mid)
                bundled_responses.append((str_mid, hashes))
            else:
                prefs = hashes

        return offset, placeholder.meta.payload.implement(identifier, prefs, bundled_responses)
