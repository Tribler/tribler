from nose.tools import raises

from Tribler.Core.Utilities.encoding import (_a_encode_int, _a_encode_long, _a_encode_float, _a_encode_unicode,
                                             _a_encode_bytes, _a_encode_list, _a_decode_true, _a_decode_false,
                                             _a_decode_none, _a_encode_set, _a_encode_none,
                                             _a_encode_bool, _a_encode_tuple, _a_encode_dictionary, bytes_to_uint,
                                             _a_decode_int, _a_decode_long, _a_decode_float,
                                             _a_decode_unicode, encode, _a_decode_bytes, _a_decode_list,
                                             _a_decode_mapping, _a_decode_set, _a_decode_tuple,
                                             _a_decode_dictionary, decode)
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestUnicode(TriblerCoreTest):

    def test_a_encode_int(self):
        result = _a_encode_int(42, None)
        self.assertEqual(result, ('2', 'i', '42'))

    @raises(AssertionError)
    def test_a_encode_int_wrong_type(self):
        _a_encode_int('42', None)

    def test_a_encode_long(self):
        result = _a_encode_long(42L, None)
        self.assertEqual(result, ('2', 'J', '42'))

    @raises(AssertionError)
    def test_a_encode_long_wrong_type(self):
        _a_encode_long(42, None)

    def test_a_encode_float(self):
        result = _a_encode_float(42.0, None)
        self.assertEqual(result, ('4', 'f', '42.0'))

    @raises(AssertionError)
    def test_a_encode_float_wrong_type(self):
        _a_encode_float(42, None)

    def test_a_encode_unicode(self):
        result = _a_encode_unicode(u'foo-bar', None)
        self.assertEqual(result, ('7', 's', 'foo-bar'))

    @raises(AssertionError)
    def test_a_encode_unicode_wrong_type(self):
        _a_encode_unicode('7', None)

    def test_a_encode_bytes(self):
        result = _a_encode_bytes('foo-bar', None)
        self.assertEqual(result, ('7', 'b', 'foo-bar'))

    @raises(AssertionError)
    def test_a_encode_bytes_wrong_type(self):
        _a_encode_bytes(u'7', None)

    def test_a_encode_list(self):
        result = _a_encode_list([1, 2, 3], { int: lambda i, _: ['1', 'i', str(i)] })
        self.assertEqual(result, ['3', 'l', '1', 'i', '1', '1', 'i', '2', '1', 'i', '3'])

    @raises(AssertionError)
    def test_a_encode_list_wrong_type(self):
        _a_encode_list({}, None)

    def test_a_encode_set(self):
        result = _a_encode_set({1, 2, 3}, { int: lambda i, _: ['1', 'i', str(i)] })
        self.assertEqual(result, ['3', 'L', '1', 'i', '1', '1', 'i', '2', '1', 'i', '3'])

    @raises(AssertionError)
    def test_a_encode_set_wrong_type(self):
        _a_encode_set([], None)

    def test_a_encode_tuple(self):
        result = _a_encode_tuple((1, 2), { int: lambda i, _: ['1', 'i', str(i)] })
        self.assertEqual(result, ['2', 't', '1', 'i', '1', '1', 'i', '2'])

    @raises(AssertionError)
    def test_a_encode_tuple_wrong_type(self):
        _a_encode_tuple([], None)

    def test_a_encode_dictionary(self):
        result = _a_encode_dictionary({'foo':'bar', 'moo':'milk'}, { str: lambda s, _: [str(len(s)), 's', s] })
        self.assertEqual(result, ['2', 'd', '3', 's', 'foo', '3', 's', 'bar', '3', 's', 'moo', '4', 's', 'milk'])

    @raises(AssertionError)
    def test_a_encode_dictionary_wrong_type(self):
        _a_encode_dictionary([], None)

    def test_a_encode_none(self):
        result = _a_encode_none(None, None)
        self.assertEqual(result, ['0n'])

    def test_a_encode_bool(self):
        result = _a_encode_bool(True, None)
        self.assertEqual(result, ['0T'])
        result = _a_encode_bool(False, None)
        self.assertEqual(result, ['0F'])

    def test_bytes_to_uint(self):
        result = bytes_to_uint("abcd")
        self.assertEqual(result, 97)

    def test_encode(self):
        result = encode(42, 'a')
        self.assertEqual(result, 'a2i42')

    @raises(ValueError)
    def test_encode_wrongversion(self):
        encode(42, 'b')

    # Decoding
    def test_a_decode_int(self):
        result = _a_decode_int('a2i42', 3, 2, None)
        self.assertEqual(result, (5, 42))

    def test_a_decode_long(self):
        result = _a_decode_long('a2J42', 3, 2, None)
        self.assertEqual(result, (5, 42))

    def test_a_decode_float(self):
        result = _a_decode_float('a3f4.2', 3, 3, None)
        self.assertEqual(result, (6, 4.2))

    def test_a_decode_unicode(self):
        result = _a_decode_unicode('a3sbar', 3, 3, None)
        self.assertEqual(result, (6, u'bar'))

    @raises(ValueError)
    def test_a_decode_unicode_outrange(self):
        _a_decode_unicode('a3sbar', 4, 3, None)

    def test_a_decode_bytes(self):
        result = _a_decode_bytes('a3bfoo', 3, 3, None)
        self.assertEqual(result, (6, u'foo'))

    @raises(ValueError)
    def test_a_decode_bytes_outrange(self):
        _a_decode_bytes('a3bfoo', 4, 3, None)

    def test_a_decode_list(self):
        result = _a_decode_list('a1l3i123', 3, 1, _a_decode_mapping)
        self.assertEqual(result, (8, [123]))

    def test_a_decode_set(self):
        result = _a_decode_set('a1L3i123', 3, 1, _a_decode_mapping)
        self.assertEqual(result, (8, {123}))

    def test_a_decode_tuple(self):
        result = _a_decode_tuple('a1t3i123', 3, 1, _a_decode_mapping)
        self.assertEqual(result, (8, (123,)))

    def test_a_decode_dictionary(self):
        result = _a_decode_dictionary('a2d3sfoo3sbar3smoo4smilk', 3, 2, _a_decode_mapping)
        self.assertEqual(result, (24,{'foo':'bar','moo':'milk'}))

    @raises(ValueError)
    def test_a_decode_dictionary_dupkey(self):
        _a_decode_dictionary('a2d3sfoo3sbar3sfoo4smilk', 3, 2, _a_decode_mapping)

    def test_a_decode_none(self):
        result = _a_decode_none(None, 5, 0, None)
        self.assertEqual(result, (5, None))

    @raises(AssertionError)
    def test_a_decode_none_nonzero_count(self):
        _a_decode_none(None, 5, 1, None)

    def test_a_decode_true(self):
        result = _a_decode_true(None, 5, 0, None)
        self.assertEqual(result, (5, True))

    @raises(AssertionError)
    def test_a_decode_true_nonzero_count(self):
        _a_decode_true(None, 5, 1, None)

    def test_a_decode_false(self):
        result = _a_decode_false(None, 5, 0, None)
        self.assertEqual(result, (5, False))

    @raises(AssertionError)
    def test_a_decode_false_nonzero_count(self):
        _a_decode_false(None, 5, 1, None)

    @raises(AssertionError)
    def test_decode_wrong_stream_type(self):
        decode(["a", "b"])

    @raises(AssertionError)
    def test_decode_wrong_offset_type(self):
        decode("abc", "42")

    @raises(ValueError)
    def test_decode_wrong_version_num(self):
        decode("b2i42", 0)

    def test_decode(self):
        self.assertEqual(decode("a2d3sfoo3sbar3smoo4smilk", 0), (24, {'foo': 'bar', 'moo': 'milk'}))
