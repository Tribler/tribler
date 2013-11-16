from Tribler.dispersy.payload import Payload, IntroductionRequestPayload
from Tribler.dispersy.bloomfilter import BloomFilter

MAXLONG128 = (1 << 1024) - 1
MAXLONG256 = (1 << 2048) - 1

# HSearchCommunity
class SimilarityRequest(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, key_n, preference_list):
            assert isinstance(identifier, int), type(identifier)
            assert not key_n or isinstance(key_n, long), 'key_n should be long'
            assert not preference_list or isinstance(preference_list, list), 'preferencelist should be list'
            if preference_list:
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)

            self._identifier = identifier
            self._key_n = key_n
            self._preference_list = preference_list

        @property
        def identifier(self):
            return self._identifier

        @property
        def key_n(self):
            return self._key_n

        @property
        def preference_list(self):
            return self._preference_list

class EncryptedResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, preference_list, his_preference_list):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(preference_list, list), 'preferencelist should be list not %s' % type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)

                assert isinstance(his_preference_list, list), 'his_preference_list should be list not %s' % type(his_preference_list)
                for hpreference in his_preference_list:
                    assert isinstance(hpreference, str), type(hpreference)
                    assert len(hpreference) == 20, len(hpreference)

            super(EncryptedResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._preference_list = preference_list
            self._his_preference_list = his_preference_list

        @property
        def identifier(self):
            return self._identifier

        @property
        def preference_list(self):
            return self._preference_list

        @property
        def his_preference_list(self):
            return self._his_preference_list

class BundledEncryptedResponsePayload(EncryptedResponsePayload):
    class Implementation(EncryptedResponsePayload.Implementation):
        def __init__(self, meta, identifier, my_response, bundled_responses):
            EncryptedResponsePayload.Implementation.__init__(self, meta, identifier, my_response[0], my_response[1])

            assert isinstance(bundled_responses, list), 'bundled_responses should be list not %s' % type(bundled_responses)
            assert len(bundled_responses) == len(set(mid for mid, _ in bundled_responses)), 'bundled_responses should not contain more than one entry per mid'

            for candidate_mid, response in bundled_responses:
                assert isinstance(candidate_mid, str), 'candidate_mid should be str'
                assert len(candidate_mid) == 20, len(candidate_mid)

                assert isinstance(response, tuple), type(response)
                assert len(response) == 2, len(response)

                preference_list, his_preference_list = response
                assert isinstance(preference_list, list), 'preferencelist should be list not %s' % type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)

                assert isinstance(his_preference_list, list), 'his_preference_list should be list not %s' % type(his_preference_list)
                for hpreference in his_preference_list:
                    assert isinstance(hpreference, str), type(hpreference)
                    assert len(hpreference) == 20, len(hpreference)

            self._bundled_responses = bundled_responses

        @property
        def bundled_responses(self):
            return self._bundled_responses

# ForwardCommunity
class ExtendedIntroPayload(IntroductionRequestPayload):
    class Implementation(IntroductionRequestPayload.Implementation):

        def __init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier, introduce_me_to=None):
            IntroductionRequestPayload.Implementation.__init__(self, meta, destination_address, source_lan_address, source_wan_address, advice, connection_type, sync, identifier)
            if introduce_me_to:
                assert isinstance(introduce_me_to, str), 'introduce_me_to should be str'
                assert len(introduce_me_to) == 20, len(introduce_me_to)

            self._introduce_me_to = introduce_me_to

        def set_introduce_me_to(self, introduce_me_to):
            self._introduce_me_to = introduce_me_to

        @property
        def introduce_me_to(self):
            return self._introduce_me_to

# PSearchCommunity
class EncryptedVectorPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, key_n, preference_list, global_vector):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(key_n, long), 'key_n should be long'
                assert key_n < MAXLONG128
                assert isinstance(preference_list, list), 'preference_list should be list not %s' % type(preference_list)
                for preference in preference_list:
                    assert isinstance(preference, long), type(preference)
                    assert preference < MAXLONG256

                assert isinstance(global_vector, list), 'global_vector should be list not %s' % type(preference_list)
                for item in global_vector:
                    assert isinstance(item, long), type(item)
                    assert item < MAXLONG256

            super(EncryptedVectorPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._key_n = key_n
            self._preference_list = preference_list
            self._global_vector = global_vector

        @property
        def identifier(self):
            return self._identifier

        @property
        def key_n(self):
            return self._key_n

        @property
        def preference_list(self):
            return self._preference_list

        @property
        def global_vector(self):
            return self._global_vector

class EncryptedSumPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, _sum):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(_sum, long), 'sum should be long'
                assert _sum < MAXLONG256

            super(EncryptedSumPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self.__sum = _sum

        @property
        def identifier(self):
            return self._identifier

        @property
        def _sum(self):
            return self.__sum

class EncryptedSumsPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, _sum, _sums):
            assert isinstance(_sums, list), type(_sums)
            assert len(_sums) == len(set(mid for mid, _ in _sums)), 'bundled_responses should not contain more than one entry per mid'

            if __debug__:
                assert isinstance(identifier, int), type(identifier)
                assert isinstance(_sum, long), type(_sum)
                assert _sum < MAXLONG256

                for candidate_mid, address_sum in _sums:
                    assert isinstance(candidate_mid, str), 'candidate_mid should be str'
                    assert len(candidate_mid) == 20, len(candidate_mid)
                    assert isinstance(address_sum, long), 'address_sum should be long'
                    assert address_sum < MAXLONG256

            super(EncryptedSumsPayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self.__sum = _sum
            self._sums = _sums

        @property
        def identifier(self):
            return self._identifier

        @property
        def _sum(self):
            return self.__sum

        @property
        def sums(self):
            return self._sums

# PoliSearchCommunity
class PoliSimilarityRequest(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, key_n, key_g, coefficients):
            assert isinstance(identifier, int), type(identifier)
            assert not key_n or isinstance(key_n, long), 'key_n should be long'
            assert not key_g or isinstance(key_g, long), 'key_g should be long'
            assert not coefficients or isinstance(coefficients, dict), 'preferencelist should be dict'
            if coefficients:
                for partition, coeffs in coefficients.iteritems():
                    assert isinstance(partition, int), type(partition)
                    assert partition <= 255, partition
                    assert partition >= 0, partition
                    for coeff in coeffs:
                        assert isinstance(coeff, long), type(coeff)

            self._identifier = identifier
            self._key_n = key_n
            self._key_g = key_g
            self._coefficients = coefficients

        @property
        def identifier(self):
            return self._identifier

        @property
        def key_n(self):
            return self._key_n

        @property
        def key_g(self):
            return self._key_g

        @property
        def coefficients(self):
            return self._coefficients

class EncryptedPoliResponsePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier, my_response):
            assert isinstance(identifier, int), type(identifier)
            assert isinstance(my_response, list), 'my_response should be list not %s' % type(my_response)
            for py in my_response:
                assert isinstance(py, long), type(py)

            super(EncryptedPoliResponsePayload.Implementation, self).__init__(meta)
            self._identifier = identifier
            self._my_response = my_response

        @property
        def identifier(self):
            return self._identifier

        @property
        def my_response(self):
            return self._my_response

class EncryptedPoliResponsesPayload(EncryptedPoliResponsePayload):
    class Implementation(EncryptedPoliResponsePayload.Implementation):
        def __init__(self, meta, identifier, my_response, bundled_responses):
            EncryptedPoliResponsePayload.Implementation.__init__(self, meta, identifier, my_response)

            assert isinstance(bundled_responses, list)
            assert len(bundled_responses) == len(set(mid for mid, _ in bundled_responses)), 'bundled_responses should not contain more than one entry per mid'
            for candidate_mid, response in bundled_responses:
                assert isinstance(candidate_mid, str), 'candidate_mid should be str'
                assert len(candidate_mid) == 20, len(candidate_mid)

                assert isinstance(response, list), type(response)
                for py in response:
                    assert isinstance(py, long), type(py)

            self._bundled_responses = bundled_responses

        @property
        def bundled_responses(self):
            return self._bundled_responses

# ForwardCommunity
class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            assert isinstance(identifier, int), type(identifier)

            super(PingPayload.Implementation, self).__init__(meta)
            self._identifier = identifier

        @property
        def identifier(self):
            return self._identifier

class PongPayload(PingPayload):
    pass

class SimiRevealPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, overlap):
            assert isinstance(overlap, (list, int)), type(overlap)

            super(SimiRevealPayload.Implementation, self).__init__(meta)
            self._overlap = overlap

        @property
        def overlap(self):
            return self._overlap
