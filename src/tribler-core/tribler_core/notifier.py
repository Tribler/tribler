"""
Notifier.

Author(s): Vadim Bulavintsev
"""
import logging

from tribler_common.simpledefs import NTFY


class Notifier(object):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.observers = {}

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
        if subject not in self.observers:
            self._logger.warning(f"Called notification on a non-existing subject {subject}")
            return
        for callback in self.observers[subject]:
            callback(*args)
