import logging
from asyncio import get_event_loop
from collections import defaultdict
from typing import Callable, Dict


class Notifier:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # we use type Dict for `self.observers` for providing the deterministic order of callbacks
        # Therefore `value: bool` here is unnecessary, and it just newer use.
        self.observers: Dict[str, Dict[Callable, bool]] = defaultdict(dict)

        # @ichorid:
        # We have to note the event loop reference, because when we call "notify" from an external thread,
        # we don't know anything about the existence of the event loop, and get_event_loop() can't find
        # the original event loop from an external thread.
        # We remember the event loop from the thread that runs the Notifier
        # to be able to schedule notifications from external threads
        self._loop = get_event_loop()

    def add_observer(self, topic: str, callback: Callable):
        """ Add the observer for the topic.
        Order of the added callbacks will be the same order for the calling the callbacks.
        `add_observer` doesn't support duplicated callbacks.
        """
        self.logger.debug(f"Add observer topic {topic}")
        self.observers[topic][callback] = True

    def remove_observer(self, topic: str, callback: Callable):
        """ Remove the observer from the topic. In the case of a missed callback no error will be raised.
        """
        self.logger.debug(f"Remove observer topic {topic}")
        self.observers[topic].pop(callback, None)

    def notify(self, topic: str, *args, **kwargs):
        """ Notify all observers about the topic.

        Each call of observer's callback is isolated and an exception that could
        occur in this call will not affect all other calls.
        """
        try:
            def _notify(_callback):
                _callback(*args, **kwargs)

            for callback in list(self.observers[topic]):
                # @ichorid:
                # We have to call the notifier callbacks through call_soon_threadsafe
                # because the notify method could have been called from a non-reactor thread
                self._loop.call_soon_threadsafe(_notify, callback)
        except RuntimeError as e:
            # Raises RuntimeError if called on a loop that’s been closed.
            # This can happen on a secondary thread when the main application is shutting down.
            # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe
            self.logger.warning(e)
