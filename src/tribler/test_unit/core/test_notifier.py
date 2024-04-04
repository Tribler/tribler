from unittest.mock import Mock, call

from ipv8.test.base import TestBase

from tribler.core.notifier import Notification, Notifier


class TestNotifier(TestBase):
    """
    Tests for the Notifier class.
    """

    def setUp(self) -> None:
        """
        Create a new notifier.
        """
        super().setUp()
        self.notifier = Notifier()

    def test_add_observer(self) -> None:
        """
        Test if an observer can be added and if it gets notified.
        """
        callback = Mock()
        self.notifier.add(Notification.tribler_new_version, callback)

        self.notifier.notify(Notification.tribler_new_version, version="test")

        self.assertEqual(call(version="test"), callback.call_args)

    def test_add_delegate(self) -> None:
        """
        Test if a delegate can be added and if it gets notified.
        """
        callback = Mock()
        self.notifier.delegates.add(callback)

        self.notifier.notify(Notification.tribler_new_version, version="test")

        self.assertEqual(call(Notification.tribler_new_version, version="test"), callback.call_args)

    def test_notify_too_many_args(self) -> None:
        """
        Test if notifying with too many args raises a ValueError.
        """
        def callback(version: str) -> None:
            pass

        self.notifier.add(Notification.tribler_new_version, callback)

        with self.assertRaises(ValueError):
            self.notifier.notify(Notification.tribler_new_version, version="test", other="test2")

    def test_notify_too_little_args(self) -> None:
        """
        Test if notifying with too little args raises a ValueError.
        """
        def callback(version: str) -> None:
            pass

        self.notifier.add(Notification.tribler_new_version, callback)

        with self.assertRaises(ValueError):
            self.notifier.notify(Notification.tribler_new_version)

    def test_observer_too_many_args(self) -> None:
        """
        Test if observing with too many args raises a TypeError.
        """
        def callback(version: str, other: str) -> None:
            pass

        self.notifier.add(Notification.tribler_new_version, callback)

        with self.assertRaises(TypeError):
            self.notifier.notify(Notification.tribler_new_version, version="test")

    def test_observer_too_little_args(self) -> None:
        """
        Test if observing with too little args raises a TypeError.
        """
        def callback() -> None:
            pass

        self.notifier.add(Notification.tribler_new_version, callback)

        with self.assertRaises(TypeError):
            self.notifier.notify(Notification.tribler_new_version, version="test")
