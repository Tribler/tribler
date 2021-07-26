from __future__ import annotations

import logging
from asyncio import Event, create_task, gather
from contextlib import contextmanager
from inspect import isabstract
from typing import Dict, Optional, Set, Type, TypeVar

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier


class SessionError(Exception):
    pass


class ComponentError(Exception):
    pass


class Session:
    def __init__(self, config: TriblerConfig = None, shutdown_event: Event = None, notifier: Notifier = None):
        self.config: TriblerConfig = config or TriblerConfig()
        self.shutdown_event: Event = shutdown_event or Event()
        self.notifier: Notifier = notifier or Notifier()
        self.components: Dict[Type[Component], Component] = {}
        self.trustchain_keypair = None

    async def start(self):
        for comp in self.components.values():
            await comp.start()

    async def shutdown(self):
        await gather(*[create_task(component.shutdown()) for component in self.components.values()])

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
        self.uses: Set[Component] = set()
        self.used_by: Set[Component] = set()
        self.started = Event()
        self.unused = Event()

    def _find_interfaces(self):
        result = []
        for base in reversed(self.__class__.__mro__):
            if issubclass(base, Component) and base is not Component and isabstract(base):
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
        await self.unused.wait()
        await self.shutdown()

    async def run(self):
        pass

    async def shutdown(self):
        pass

    async def use(self, interface: Type[T]) -> T:
        if self.session is None:
            raise ComponentError(f"Component {self.__class__.__name__} is not registered")
        imp = interface.imp()
        await imp.started.wait()
        self.uses.add(imp)
        imp.used_by.add(self)
        return imp

    async def unuse(self, interface: Type[T]):
        imp = interface.imp()
        self.uses.discard(imp)
        imp.used_by.discard(self)
        if not imp.used_by:
            imp.unused.set()
