import struct
import unittest

from Tribler.community.tunnel.processes.line_util import (fix_split,
                                                          pack_data,
                                                          unpack_data,
                                                          unpack_complex)

BINARY_STRING_ALL_CHARS = "".join([chr(i) for i in range(256)])


class TestLineUtil(unittest.TestCase):

    def test_fix_split_correct_single(self):
        args = [BINARY_STRING_ALL_CHARS]
        out = fix_split(1, "", args)

        self.assertEqual(out, args)

    def test_fix_split_correct_double(self):
        args = ["test", BINARY_STRING_ALL_CHARS]
        out = fix_split(2, "", args)

        self.assertEqual(out, args)

    def test_fix_split_correct_many(self):
        args = [BINARY_STRING_ALL_CHARS] * 20
        out = fix_split(20, "", args)

        self.assertEqual(out, args)

    def test_fix_split_broken_single(self):
        delim = chr(128)
        args = ["test"] + BINARY_STRING_ALL_CHARS.split(delim)
        out = fix_split(2, delim, args)

        self.assertEqual(out, ["test", BINARY_STRING_ALL_CHARS])

    def test_fix_split_broken_double(self):
        delim = chr(128)
        args = (["test"]
                + BINARY_STRING_ALL_CHARS.split(delim)
                + BINARY_STRING_ALL_CHARS.split(delim))
        out = fix_split(2, delim, args)

        self.assertEqual(out, ["test", BINARY_STRING_ALL_CHARS
                               + delim
                               + BINARY_STRING_ALL_CHARS])

    def test_pack_data_empty(self):
        out = pack_data("")

        self.assertEqual(len(out), 9)

        l = struct.unpack("Q", out[:8])[0]

        self.assertEqual(l, 1)
        self.assertEqual(out[-1], "\n")

    def test_pack_data_full(self):
        out = pack_data(BINARY_STRING_ALL_CHARS)

        self.assertEqual(len(out), len(BINARY_STRING_ALL_CHARS) + 9)

        l = struct.unpack("Q", out[:8])[0]

        self.assertEqual(l, len(BINARY_STRING_ALL_CHARS) + 1)
        self.assertEqual(out[8:-1], BINARY_STRING_ALL_CHARS)
        self.assertEqual(out[-1], "\n")

    def test_unpack_data_incomplete(self):
        data = "0000000"
        l, out = unpack_data(data)

        self.assertGreater(l, len(data))
        self.assertEqual(out, data)

    def test_unpack_data_empty(self):
        data = pack_data("")
        l, out = unpack_data(data)

        self.assertEqual(out, "")
        self.assertEqual(l, len(out) + 9)
        self.assertEqual(l, len(data))

    def test_unpack_data_full(self):
        data = pack_data(BINARY_STRING_ALL_CHARS)
        l, out = unpack_data(data)

        self.assertEqual(out, BINARY_STRING_ALL_CHARS)
        self.assertEqual(l, len(out) + 9)
        self.assertEqual(l, len(data))

    def test_unpack_complex_incomplete(self):
        data = pack_data(BINARY_STRING_ALL_CHARS)[:-2]
        keep, share = unpack_complex(data)

        self.assertEqual(keep, data)
        self.assertEqual(share, None)

    def test_unpack_complex_complete(self):
        data = pack_data(BINARY_STRING_ALL_CHARS)
        keep, share = unpack_complex(data)

        self.assertEqual(keep, "")
        self.assertEqual(share, BINARY_STRING_ALL_CHARS)

    def test_unpack_complex_overflow(self):
        remainder = "test"
        data = pack_data(BINARY_STRING_ALL_CHARS)
        keep, share = unpack_complex(data + remainder)

        self.assertEqual(keep, remainder)
        self.assertEqual(share, BINARY_STRING_ALL_CHARS)
