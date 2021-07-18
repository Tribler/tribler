"""
Author(s): Vadim Bulavintsev
"""

from asyncio import Event

from tribler_core.utilities.utilities import froze_it


class NoValue:
    # Sentinel object class
    pass


@froze_it
class ResourceLock:

    def __init__(self):
        self._users = set()
        self._resource_initialized_event = Event()
        self._resource_free = Event()
        self._resource_free.set()
        self._provided_object = NoValue

    async def add_user(self, user):
        await self._resource_initialized_event.wait()
        assert (user not in self._users)
        assert (self._provided_object is not NoValue)

        self._users.add(user)
        self._resource_free.clear()
        return self._provided_object

    def assign(self, obj):
        assert (not self._resource_initialized_event.is_set())
        assert (self._provided_object is NoValue)
        assert (self._resource_free.is_set())

        self._provided_object = obj
        self._resource_initialized_event.set()

    def release(self, user):
        assert (self._provided_object is not NoValue)

        self._users.remove(user)
        if not self._users:
            self._resource_free.set()

    @property
    def no_users(self):
        return self._resource_free.wait()
