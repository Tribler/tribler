import asyncio
import logging
from asyncio import CancelledError, Future, Task
from contextlib import suppress
from typing import Coroutine, Iterable, List, Set

from tribler.core.utilities.async_group.exceptions import CanceledException


class AsyncGroup:
    """This class is a little brother of TaskManager and his purpose is only to
    correct cancel a group asyncio Tasks/Futures

    Example:
    >>> from tribler.core.utilities.async_group.async_group import AsyncGroup
    >>> async def void():
    ...     pass
    >>> group = AsyncGroup()
    >>> group.add_task(void())
    >>> group.add_task(void())
    >>> group.add_task(void())
    >>> await group.cancel()
    """

    # This set added to prevent the potential issue described here https://github.com/Tribler/tribler/issues/7299
    # A corner case here is the following (@kozlovsky):
    #
    # It is possible that an async group itself is garbage-collected before all its tasks are finished.
    # In that case, tasks managed by this async group can be garbage collected before they are finished.
    #
    # Usually, it should not be a problem, as an async group is typically created as a field of another object
    # with a long life span. So, someone holds a reference to AsyncGroup long enough to prevent its early garbage
    # collection.
    # But theoretically, some async groups can be garbage collected too early.
    #
    # To prevent this problem all futures stores in the global set.
    _global_futures: Set[Future] = set()

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._futures: Set[Future] = set()
        self._canceled = False

    def add_task(self, coroutine: Coroutine) -> Task:
        """Add a coroutine to the group.
        """
        if self._canceled:
            raise CanceledException()

        task = asyncio.create_task(coroutine)

        self._futures.add(task)
        self._global_futures.add(task)

        task.add_done_callback(self._done_callback)
        return task

    async def wait(self):
        """ Wait for completion of all futures
        """
        if self._futures:
            await asyncio.wait(self._futures)

    async def cancel(self) -> List[Future]:
        """Cancel the group.

        Only active futures will be cancelled.
        """
        if self._canceled:
            return []

        self._canceled = True

        active = list(self._active(self._futures))
        for future in active:
            future.cancel()

        with suppress(CancelledError):
            await asyncio.gather(*active)

        return active

    @property
    def cancelled(self):
        return self._canceled

    def _done_callback(self, future: Future):
        self._futures.discard(future)
        self._global_futures.discard(future)

    @staticmethod
    def _active(futures: Iterable[Future]) -> Iterable[Future]:
        return (future for future in futures if not future.done())

    def __del__(self):
        if active := list(self._active(self._futures)):
            self._logger.error(f'AsyncGroup is destroying but {len(active)} futures are active')
