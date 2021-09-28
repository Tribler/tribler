from __future__ import annotations

import logging
import os
import sys
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
        for component in components:
            self.register(component.__class__, component)

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

    def __enter__(self):
        Session._stack.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert Session._stack and Session._stack[-1] is self
        Session._stack.pop()


T = TypeVar('T', bound='Component')


class Component:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
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
    def instance(cls: Type[T]) -> T:
        session = Session.current()
        return session.components.get(cls)

    async def start(self):
        self.logger.info(f'Start: {self.__class__.__name__}')
        try:
            await self.run()
        except Exception as e:
            # Writing to stderr is for the case when logger is not configured properly (as my happen in local tests,
            # for example) to avoid silent suppression of the important exceptions
            sys.stderr.write(f'\nException in {self.__class__.__name__}.start(): {type(e).__name__}:{e}\n')
            self.logger.exception(f'Exception in {self.__class__.__name__}.start(): {type(e).__name__}:{e}')
            self.failed = True
            self.started.set()
            raise
        self.started.set()

    async def stop(self):
        self.logger.info(f'Stop: {self.__class__.__name__}')
        self.logger.info("Waiting for other components to release me")
        await self.unused.wait()
        self.logger.info("Component free, shutting down")
        await self.shutdown()
        self.stopped = True
        for dep in list(self.components_used_by_me):
            self._release_instance(dep)
        self.logger.info("Component free, shutting down")

    async def run(self):
        pass

    async def shutdown(self):
        pass

    async def require_component(self, dependency: Type[T]) -> T:
        """ Resolve the dependency to a component.
        The method will wait the component to be initialised.

        Returns:    The component instance.
                    In case of a missed or failed dependency an exception will be raised.
        """
        dep = await self.get_component(dependency)
        if not dep:
            raise ComponentError(
                f'Missed dependency: {self.__class__.__name__} requires {dependency.__name__} to be active')
        return dep

    async def get_component(self, dependency: Type[T]) -> Optional[T]:
        """ Resolve the dependency to a component.
        The method will wait the component to be initialised.

        Returns:    The component instance.
                    In case of a missed or failed dependency None will be returned.
        """
        dep = dependency.instance()
        if not dep:
            return None

        await dep.started.wait()
        if dep.failed:
            self.logger.warning(f'Component {self.__class__.__name__} has failed dependency {dependency.__name__}')
            return None

        self.components_used_by_me.add(dep)
        dep.in_use_by.add(self)
        return dep

    def release_component(self, dependency: Type[T]):
        dep = dependency.instance()
        if dep:
            self._release_instance(dep)

    def _release_instance(self, dep: Component):
        assert dep in self.components_used_by_me
        self.components_used_by_me.discard(dep)
        dep.in_use_by.discard(self)
        if not dep.in_use_by:
            dep.unused.set()
