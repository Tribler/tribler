import asyncio
from asyncio import CancelledError, Future, Task
from contextlib import suppress
from typing import Iterable, List, Set


class AsyncGroup:
    """This class is a little brother of TaskManager and his purpose is only to
    correct cancel a group asyncio Tasks/Futures

    Example:
    >>> from tribler.core.utilities.async_group import AsyncGroup
    >>> async def void():
    ...     pass
    >>> group = AsyncGroup()
    >>> group.add_task([
    ...     void(),
    ...     void(),
    ...     void()
    ... ])
    >>> await group.cancel()
    """

    def __init__(self):
        self._futures: Set[Future] = set()

    def add_task(self, *coroutines) -> List[Task]:
        """Add a coroutine to the group.
        """
        result = []
        for coroutine in coroutines:
            task = asyncio.create_task(coroutine)
            self._futures.add(task)
            task.add_done_callback(self._done_callback)
            result.append(task)

        return result

    async def wait(self):
        """ Wait for completion of all futures
        """
        if self._futures:
            await asyncio.wait(self._futures)

    async def cancel(self) -> List[Future]:
        """Cancel the group.

        Only active futures will be cancelled.
        """
        active = list(self._active(self._futures))
        for future in active:
            future.cancel()

        with suppress(CancelledError):
            await asyncio.gather(*active)

        return active

    def _done_callback(self, future: Future):
        self._futures.remove(future)

    @staticmethod
    def _active(futures: Iterable[Future]) -> Iterable[Future]:
        return (future for future in futures if not future.done())
