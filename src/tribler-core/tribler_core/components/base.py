from __future__ import annotations

import logging
from asyncio import Event, create_task, gather, get_event_loop
from contextlib import contextmanager
from typing import Dict, List, Optional, Iterable, Set, Type, TypeVar

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier


class SessionError(Exception):
    pass


class ComponentError(Exception):
    pass


class Session:
    def __init__(self, config: TriblerConfig = None, components: Iterable[Component] = (), shutdown_event: Event = None,
                 notifier: Notifier = None):
        self.config: TriblerConfig = config or TriblerConfig()
        self.shutdown_event: Event = shutdown_event or Event()
        self.notifier: Notifier = notifier or Notifier()
        self.components: Dict[Type[Component], Component] = {}
        self.trustchain_keypair = None
        for comp in components:
            comp.register(self)

    async def start(self):
        loop = get_event_loop()
        started_events: List[Event] = []
        for comp in self.components.values():
            loop.create_task(comp.start())
            started_events.append(comp.started)
        await gather(*[event.wait() for event in started_events])

    async def shutdown(self):
        await gather(*[create_task(component.stop()) for component in self.components.values()])


_default_session: Optional[Session] = None


def _get_default_session() -> Session:
    if _default_session is None:
        raise SessionError("Default session was not set")
    return _default_session


def set_default_session(session: Session):
    global _default_session
    _default_session = session


_session_stack = []


@contextmanager
def with_session(session: Session):
    _session_stack.append(session)
    yield
    assert _session_stack and _session_stack[-1] is session
    _session_stack.pop()


def get_session() -> Session:
    if _session_stack:
        return _session_stack[-1]
    return _get_default_session()


T = TypeVar('T', bound='Component')


class Component:
    def __init__(self):
        cls = self.__class__
        self.logger = logging.getLogger(cls.__name__)
        self.logger.info('__init__')
        self.session: Optional[Session] = None
        self.interfaces = self._find_interfaces()
        if not self.interfaces:
            raise ComponentError(f'Interface class not found for {cls.__name__}')
        self.components_used_by_me: Set[Component] = set()
        self.in_use_by: Set[Component] = set()
        self.started = Event()
        self.unused = Event()
        # Every component starts unused, so it does not lock the whole system on shutdown
        self.unused.set()

    def _find_interfaces(self):
        cls = self.__class__
        result = []
        for base in reversed(self.__class__.__mro__):
            if issubclass(base, Component) and base not in (Component, cls) and base.__name__.endswith('Component'):
                result.append(base)
        return result

    @classmethod
    def _find_implementation(cls: Type[T]) -> T:
        session = get_session()
        imp = session.components.get(cls)
        if imp is None:
            raise ComponentError(f"Component implementation not found for {cls.__name__} in session {session}")
        return imp

    @classmethod
    def imp(cls: Type[T]) -> T:
        return cls._find_implementation()

    def register(self, session: Session = None):
        self.logger.info('Register')
        if self.session is not None:
            raise ComponentError(f'Component {self} is already registered at session {self.session}')

        session = session or get_session()
        self.session = session

        for interface in self.interfaces:
            if session.components.get(interface, self) is not self:
                raise ComponentError(f'Component interface {interface.__name__} '
                                     f'already registered in session {session}')

        for interface in self.interfaces:
            session.components[interface] = self

    async def start(self):
        await self.run()
        self.started.set()

    async def stop(self):
        self.logger.info(f"Waiting for other components to release me")
        await self.unused.wait()
        self.logger.info(f"Component free, shutting down")
        await self.shutdown()
        await gather(*[self._release_imp(imp) for imp in list(self.components_used_by_me)])

    async def run(self):
        pass

    async def shutdown(self):
        pass

    async def use(self, dependency: Type[T]) -> T:
        dep = dependency.imp()

        self.components_used_by_me.add(dep)
        await dep.started.wait()
        dep.in_use_by.add(self)
        return dep

    async def _release_imp(self, dep: Component):
        assert (dep in self.components_used_by_me)
        self.components_used_by_me.discard(dep)
        dep.in_use_by.discard(self)
        if not dep.in_use_by:
            dep.unused.set()

    async def release(self, dependency: Type[T]):
        dep = dependency.imp()
        await self._release_imp(dep)
