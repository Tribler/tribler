import logging

from tribler_core.resource_lock import ResourceLock
from tribler_core.session import Mediator
from tribler_core.utilities.utilities import froze_it


@froze_it
class Component:
    role = None

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Init')
        self._used_resources = set()
        self._provided_object = None
        self._resource_lock = ResourceLock()

    async def unused(self):
        await self._resource_lock.no_users

    def prepare_futures(self, mediator: Mediator):
        pass

    async def run(self, mediator: Mediator):
        self.logger.info('Run')

    async def shutdown(self, mediator: Mediator):
        self.logger.info('Shutdown')
        for label in self._used_resources:
            self.release_dependency(mediator, label)

    async def use(self, mediator: Mediator, label):
        assert (label not in self._used_resources)
        self._used_components.add(label)
        return await mediator.awaitable_components[label].add_user(self.__class__)

    def provide(self, mediator: Mediator, obj):
        assert (self._provided_object is None)
        self._provided_object = obj
        mediator.awaitable_components[self.role].assign(obj)

    def release_dependency(self, mediator: Mediator, label):
        assert (label in self._used_resources)
        self._used_resources.remove(label)
        mediator.awaitable_components[label].release(self.role)
