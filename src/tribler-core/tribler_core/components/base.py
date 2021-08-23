from __future__ import annotations

import logging
import os
import sys
from abc import abstractmethod
from asyncio import Event, create_task, gather
from itertools import count
from pathlib import Path
from typing import Dict, List, Optional, Set, Type, TypeVar

from tribler_common.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_DB_DIR

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path


class SessionError(Exception):
    pass


class ComponentError(Exception):
    pass


def create_state_directory_structure(state_dir: Path):
    """Create directory structure of the state directory."""
    state_dir.mkdir(exist_ok=True)
    (state_dir / STATEDIR_DB_DIR).mkdir(exist_ok=True)
    (state_dir / STATEDIR_CHANNELS_DIR).mkdir(exist_ok=True)


class Session:
    _next_session_id = count(1)
    _default: Optional[Session] = None
    _stack: List[Session] = []

    def __init__(self, config: TriblerConfig = None, components: List[Component] = (),
                 shutdown_event: Event = None, notifier: Notifier = None):
        # deepcode ignore unguarded~next~call: not necessary to catch StopIteration on infinite iterator
        self.id = next(Session._next_session_id)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config: TriblerConfig = config or TriblerConfig()
        self.shutdown_event: Event = shutdown_event or Event()
        self.notifier: Notifier = notifier or Notifier()
        self.components: Dict[Type[Component], Component] = {}
        for implementation in components:
            self.register(implementation.interface, implementation)

    def __repr__(self):
        return f'<{self.__class__.__name__}:{self.id}>'

    @staticmethod
    def _get_default_session() -> Session:
        if Session._default is None:
            raise SessionError("Default session was not set")
        return Session._default

    def set_as_default(self):
        Session._default = self

    @staticmethod
    def unset_default_session():
        Session._default = None

    @staticmethod
    def current() -> Session:
        if Session._stack:
            return Session._stack[-1]
        return Session._get_default_session()

    def register(self, comp_cls: Type[Component], comp: Component):
        if comp.session is not None:
            raise ComponentError(f'Component {comp.__class__.__name__} is already registered in session {comp.session}')
        if comp_cls in self.components:
            raise ComponentError(f'Component class {comp_cls.__name__} is already registered in session {self}')
        self.components[comp_cls] = comp
        comp.session = self

    async def start(self, failfast=True):
        self.logger.info("Session is using state directory: %s", self.config.state_dir)
        create_state_directory_structure(self.config.state_dir)
        patch_crypto_be_discovery()
        # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
        # certificates provided by the system trust store.
        if sys.platform == 'darwin':
            os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

        coros = [comp.start() for comp in self.components.values()]
        await gather(*coros, return_exceptions=not failfast)

    async def shutdown(self):
        await gather(*[create_task(component.stop()) for component in self.components.values()])

    def get(self, interface: Type[T]) -> T:
        imp = self.components.get(interface)
        if imp is None:
            raise ComponentError(f"{interface.__name__} implementation not found in {self}")
        return imp

    def __enter__(self):
        Session._stack.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert Session._stack and Session._stack[-1] is self
        Session._stack.pop()


T = TypeVar('T', bound='Component')


class Component:
    enable_in_gui_test_mode = False
    enabled = True

    def __init__(self, interface: Type[Component]):
        assert isinstance(self, interface)
        self.interface = interface
        self.logger = logging.getLogger(interface.__name__)
        self.logger.info('__init__')
        self.session: Optional[Session] = None
        self.components_used_by_me: Set[Component] = set()
        self.in_use_by: Set[Component] = set()
        self.started = Event()
        self.failed = False
        self.unused = Event()
        self.stopped = False
        # Every component starts unused, so it does not lock the whole system on shutdown
        self.unused.set()

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):  # pylint: disable=unused-argument
        return False

    @classmethod
    @abstractmethod
    def make_implementation(cls: Type[T], config, enable) -> T:
        assert False, f"Abstract classmethod make_implementation not implemented in class {cls.__name__}"

    @classmethod
    def _find_implementation(cls: Type[T]) -> T:
        session = Session.current()
        return session.get(cls)

    @classmethod
    def imp(cls: Type[T]) -> T:
        return cls._find_implementation()

    async def start(self):
        try:
            await self.run()
        except Exception as e:
            print(f'\n*** Exception in {self.__class__.__name__}.start(): {type(e).__name__}:{e}\n')
            self.logger.exception(f'Exception in {self.__class__.__name__}.start(): {type(e).__name__}:{e}')
            self.failed = True
            self.started.set()
            raise
        self.started.set()

    async def stop(self):
        self.logger.info("Waiting for other components to release me")
        await self.unused.wait()
        self.logger.info("Component free, shutting down")
        await self.shutdown()
        self.stopped = True
        for dep in list(self.components_used_by_me):
            self._release_imp(dep)
        self.logger.info("Component free, shutting down")

    async def run(self):
        pass

    async def shutdown(self):
        pass

    async def use(self, dependency: Type[T]) -> T:
        dep = dependency.imp()
        await dep.started.wait()
        if dep.failed:
            raise ComponentError(f'Component {self.__class__.__name__} has failed dependency {dep.__class__.__name__}')
        self.components_used_by_me.add(dep)
        dep.in_use_by.add(self)
        return dep

    def _release_imp(self, dep: Component):
        assert dep in self.components_used_by_me
        self.components_used_by_me.discard(dep)
        dep.in_use_by.discard(self)
        if not dep.in_use_by:
            dep.unused.set()

    async def release(self, dependency: Type[T]):
        dep = dependency.imp()
        self._release_imp(dep)


def testcomponent(component_cls):
    component_cls.enabled = False
    return component_cls
