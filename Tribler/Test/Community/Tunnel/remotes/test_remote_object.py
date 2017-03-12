import unittest

from Tribler.community.tunnel.remotes.remote_object import RemoteObject, shared

BINARY_STRING_ALL_CHARS = "".join([chr(i) for i in range(256)])


class MockShared(RemoteObject):

    @shared
    def shared_normal(self):
        pass

    @shared()
    def shared_normal_parentheses(self):
        pass

    @shared(False)
    def shared_normal_explicit(self):
        pass

    @shared(True)
    def shared_id(self):
        pass


class TestRemoteObject(unittest.TestCase):

    def test_dirty_startup(self):
        mock = MockShared()

        self.assertFalse(mock.__is_dirty__())

    def test_dirty_changed_normal(self):
        mock = MockShared()
        mock.shared_normal = "test"

        self.assertTrue(mock.__is_dirty__())

    def test_dirty_changed_normal_parentheses(self):
        mock = MockShared()
        mock.shared_normal_parentheses = "test"

        self.assertTrue(mock.__is_dirty__())

    def test_dirty_changed_normal_explicit(self):
        mock = MockShared()
        mock.shared_normal_explicit = "test"

        self.assertTrue(mock.__is_dirty__())

    def test_dirty_changed_shared_id(self):
        mock = MockShared()
        mock.shared_id = "test"

        self.assertTrue(mock.__is_dirty__())

    def test_serialize_with_bool(self):
        mock = MockShared()
        mock.shared_normal = True

        s = MockShared.__serialize__(mock)
        _, out = MockShared.__unserialize__(s)

        self.assertEqual(out.shared_normal, True)

    def test_serialize_with_int(self):
        mock = MockShared()
        mock.shared_normal = 3

        s = MockShared.__serialize__(mock)
        _, out = MockShared.__unserialize__(s)

        self.assertEqual(out.shared_normal, 3)

    def test_serialize_with_float(self):
        mock = MockShared()
        mock.shared_normal = 3.14

        s = MockShared.__serialize__(mock)
        _, out = MockShared.__unserialize__(s)

        self.assertEqual(out.shared_normal, 3.14)

    def test_serialize_with_str(self):
        mock = MockShared()
        mock.shared_normal = BINARY_STRING_ALL_CHARS

        s = MockShared.__serialize__(mock)
        _, out = MockShared.__unserialize__(s)

        self.assertEqual(out.shared_normal, BINARY_STRING_ALL_CHARS)

    def test_serialize_with_list(self):
        a = [True, 3, 3.14, BINARY_STRING_ALL_CHARS]

        mock = MockShared()
        mock.shared_normal = a

        s = MockShared.__serialize__(mock)
        _, out = MockShared.__unserialize__(s)

        self.assertListEqual(out.shared_normal, a)

    def test_serialize_with_complex_nested(self):
        mock = MockShared()
        mock.shared_normal = [[chr(255),],]

        s = MockShared.__serialize__(mock)

        self.assertEqual(s, "")

    def test_serialize_with_pointer(self):
        mock = MockShared()
        mock.shared_normal = lambda _: None

        with self.assertRaises(TypeError):
            MockShared.__serialize__(mock)

    def test_serialize_only_update_size(self):
        mock = MockShared()
        mock.shared_normal = "test"

        dirty = MockShared.__serialize__(mock)
        clean = MockShared.__serialize__(mock)

        self.assertLess(len(clean), len(dirty))

    def test_serialize_only_update(self):
        mock = MockShared()
        mock.shared_normal = "test"

        dirty = MockShared.__serialize__(mock, True)
        full = MockShared.__serialize__(mock, False)

        _, out_dirty = MockShared.__unserialize__(dirty)
        _, out_full = MockShared.__unserialize__(full)

        self.assertEqual(out_dirty.shared_normal, "test")
        self.assertEqual(out_dirty.shared_normal, out_full.shared_normal)

    def test_unserialize_unknown(self):
        known = {"test2": MockShared()}
        mock = MockShared()
        mock.shared_id = "test"

        s = MockShared.__serialize__(mock)
        out_id, out = MockShared.__unserialize__(s, known)

        self.assertEqual(out_id, "test")
        self.assertEqual(out_id, mock.shared_id)
        self.assertNotEqual(out, known["test2"])

    def test_unserialize_known(self):
        known = {"test": MockShared()}
        mock = MockShared()
        mock.shared_id = "test"

        s = MockShared.__serialize__(mock)
        out_id, out = MockShared.__unserialize__(s, known)

        self.assertEqual(out_id, "test")
        self.assertEqual(out_id, mock.shared_id)
        self.assertEqual(out, known["test"])

    def test_extract_class_name(self):
        mock = MockShared()

        s = MockShared.__serialize__(mock)
        out = RemoteObject.__extract_class_name__(s)

        self.assertEqual(out, "MockShared")
