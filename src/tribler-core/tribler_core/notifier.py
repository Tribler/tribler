import logging
from asyncio import get_event_loop
from collections import defaultdict
from typing import Callable, Dict


class Notifier:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.observers: Dict[str, set] = defaultdict(set)
        # @ichorid:
        # We have to note the event loop reference, because when we call "notify" from an external thread,
        # we don't know anything about the existence of the event loop, and get_event_loop() can't find
        # the original event loop from an external thread.
        # We remember the event loop from the thread that runs the Notifier
        # to be able to schedule notifications from external threads
        self._loop = get_event_loop()

    def add_observer(self, topic: str, callback: Callable):
        self.logger.debug(f"Add observer topic {topic}")
        self.observers[topic].add(callback)

    def remove_observer(self, topic: str, callback: Callable):
        self.logger.debug(f"Remove observer topic {topic}")
        self.observers[topic].discard(callback)

    def notify(self, topic: str, *args, **kwargs):
        def _notify(_topic, _kwargs, *_args):
            for callback in self.observers[_topic]:
                try:
                    callback(*_args, **_kwargs)
                except Exception as _e:  # pylint: disable=broad-except
                    self.logger.exception(_e)

        try:
            # @ichorid:
            # We have to call the notifier callbacks through call_soon_threadsafe
            # because the notify method could have been called from a non-reactor thread
            self._loop.call_soon_threadsafe(_notify, topic, kwargs, *args)
        except RuntimeError as e:
            # Raises RuntimeError if called on a loop that’s been closed.
            # This can happen on a secondary thread when the main application is shutting down.
            # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe
            self.logger.warning(e)
