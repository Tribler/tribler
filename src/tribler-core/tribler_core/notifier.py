"""
Notifier.

Author(s): Vadim Bulavintsev
"""
import logging
from asyncio import get_event_loop

from tribler_common.simpledefs import NTFY


class Notifier:

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.observers = {}
        # We have to note the event loop reference, because when we call "notify" from an external thread,
        # we don't know anything about the existence of the event loop, and get_event_loop() can't find
        # the original event loop from an external thread.
        self._loop = get_event_loop()
        # We remember the event loop from the thread that runs the Notifier
        # to be able to schedule notifications from external threads

    def add_observer(self, subject, callback):
        assert isinstance(subject, NTFY)
        self.observers[subject] = self.observers.get(subject, [])
        self.observers[subject].append(callback)
        self._logger.debug(f"Add observer topic {subject} callback {callback}")

    def remove_observer(self, subject, callback):
        if subject not in self.observers:
            return
        if callback not in self.observers[subject]:
            return

        self.observers[subject].remove(callback)
        self._logger.debug(f"Remove observer topic {subject} callback {callback}")

    def notify(self, subject, *args):
        # We have to call the notifier callbacks through call_soon_threadsafe
        # because the notify method could have been called from a non-reactor thread
        self._loop.call_soon_threadsafe(self._notify, subject, *args)

    def _notify(self, subject, *args):
        if subject not in self.observers:
            self._logger.warning(f"Called notification on a non-existing subject {subject}")
            return
        for callback in self.observers[subject]:
            callback(*args)

    def notify_shutdown_state(self, state):
        self._logger.info("Tribler shutdown state notification:%s", state)
        self.notify(NTFY.TRIBLER_SHUTDOWN_STATE, state)
