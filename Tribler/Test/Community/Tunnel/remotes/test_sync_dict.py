import unittest

from Tribler.community.tunnel.remotes.remote_object import RemoteObject, shared
from Tribler.community.tunnel.remotes.sync_dict import SyncDict


class MockShared(RemoteObject):

    @shared
    def field1(self):
        pass

    @shared
    def field2(self):
        pass

    @shared(True)
    def field_id(self):
        pass


class TestSyncDict(unittest.TestCase):

    def setUp(self):
        self.called = False

    def test_is_same_type(self):
        sync_dict = SyncDict(MockShared)

        self.assertTrue(sync_dict.is_same_type(MockShared.__name__))

    def test_is_not_same_type(self):
        sync_dict = SyncDict(MockShared)

        self.assertFalse(sync_dict.is_same_type(SyncDict.__name__))

    def test_callback_when_dirty(self):
        def callback(_):
            self.called = True

        sync_dict = SyncDict(MockShared, callback=callback)
        mock = MockShared()
        mock.field_id = "test"
        sync_dict[mock.field_id] = mock

        sync_dict.synchronize()

        self.assertTrue(self.called)

    def test_no_callback_when_not_dirty(self):
        def callback(_):
            self.called = True

        sync_dict = SyncDict(MockShared, callback=callback)

        sync_dict.synchronize()

        self.assertFalse(self.called)

    def test_on_synchronize(self):
        sync_dict2 = SyncDict(MockShared)
        sync_dict = SyncDict(MockShared,
                             callback=sync_dict2.on_synchronize)
        mock = MockShared()
        mock.field_id = "test"
        sync_dict[mock.field_id] = mock

        self.assertNotIn(mock.field_id, sync_dict2)

        sync_dict.synchronize()

        self.assertIn(mock.field_id, sync_dict2)

    def test_synchronize_only_update(self):
        sync_dict2 = SyncDict(MockShared)
        sync_dict = SyncDict(MockShared,
                             callback=sync_dict2.on_synchronize)
        mock = MockShared()
        mock.field_id = "test"
        mock.field1 = "a"
        mock.field2 = "b"
        sync_dict[mock.field_id] = mock

        sync_dict.synchronize(False)

        self.assertEqual(sync_dict2[mock.field_id].field1, "a")
        self.assertEqual(sync_dict2[mock.field_id].field2, "b")

        sync_dict2[mock.field_id].field1 = "x"
        sync_dict2[mock.field_id].field2 = "d"
        mock.field1 = "c"

        sync_dict.synchronize(True)

        self.assertEqual(sync_dict2[mock.field_id].field1, "c")
        self.assertEqual(sync_dict2[mock.field_id].field2, "d")
