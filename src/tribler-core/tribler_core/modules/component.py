import logging

from tribler_core.awaitable_resources import ComponentRoleType
from tribler_core.mediator import Mediator


class Component:
    role = None

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Init')
        self._used_resources = set()
        self._provided_object = None

    async def unused(self, mediator):
        await mediator.optional[self.role].no_users

    async def run(self, mediator: Mediator):
        self.logger.info('Run')

    async def shutdown(self, mediator: Mediator):
        self.logger.info('Shutdown')
        for role in list(self._used_resources):
            self.release_dependency(mediator, role)

    async def use(self, mediator: Mediator, role: ComponentRoleType):
        assert (role not in self._used_resources)
        self._used_resources.add(role)
        return await mediator.optional[role].add_user(self.role)

    def provide(self, mediator: Mediator, obj):
        assert (self._provided_object is None)
        self._provided_object = obj
        mediator.optional[self.role].assign(obj)

    def release_dependency(self, mediator: Mediator, role: ComponentRoleType):
        assert (role in self._used_resources)
        self._used_resources.remove(role)
        mediator.optional[role].release(self.role)
