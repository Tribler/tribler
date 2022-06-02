import asyncio
from asyncio import CancelledError, Future
from contextlib import suppress
from typing import Iterable, List, Set


class AsyncGroup:
    """This class is a little brother of TaskManager and his purpose is only to
    correct cancel a group asyncio Tasks/Futures

    Example:
    >>> import asyncio
    >>> from tribler.core.utilities.async_group import AsyncGroup
    >>> async def void():
    ...     pass
    >>> group = AsyncGroup()
    >>> group.add([
    ...     asyncio.create_task(void()),
    ...     asyncio.create_task(void()),
    ...     asyncio.create_task(void())
    ... ])
    >>> await group.cancel()
    """

    def __init__(self):
        self._futures: Set[Future] = set()

    def add(self, *coroutines):
        """Add a coroutine to the group.
        """
        for coroutine in coroutines:
            task = asyncio.create_task(coroutine)
            self._futures.add(task)
            task.add_done_callback(self._done_callback)

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
