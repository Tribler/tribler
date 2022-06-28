from __future__ import annotations

import logging
import os
import sys
from asyncio import Event, create_task, gather, get_event_loop
from contextlib import asynccontextmanager
from itertools import count
from typing import Dict, List, Optional, Type, TypeVar

from tribler.core.components.base import Component, ComponentError, create_state_directory_structure, reserve_ports
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler.core.utilities.install_dir import get_lib_path
from tribler.core.utilities.notifier import Notifier


class SessionError(Exception):
    pass


@asynccontextmanager
async def session_manager(session: Session):
    """ Session context manager automates routine operations on session object.

    In simple terms, it does the following things:
    1. Set the current session as a default session
    2. Call await session.start_components()
    2. Call await session.shutdown()

    Example of use:
        ...
        async with Session(config, components).start():
            print(session.current())
        ...
    """
    with session:  # set the current session as a default session
        try:
            await session.start_components()  # on enter
            yield session
        finally:
            await session.shutdown()  # on leave


class Session:
    _next_session_id = count(1)
    _default: Optional[Session] = None
    _stack: List[Session] = []
    _startup_exception: Optional[Exception] = None

    def __init__(self, config: TriblerConfig = None, components: List[Component] = (),
                 shutdown_event: Event = None, notifier: Notifier = None, failfast: bool = True):
        # deepcode ignore unguarded~next~call: not necessary to catch StopIteration on infinite iterator
        self.id = next(Session._next_session_id)
        self.failfast = failfast
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config: TriblerConfig = config or TriblerConfig()
        self.shutdown_event: Event = shutdown_event or Event()
        self.notifier: Notifier = notifier or Notifier()
        self.components: Dict[Type[Component], Component] = {}
        for component in components:
            self.register(component.__class__, component)

        # Reserve various (possibly) fixed ports to prevent
        # components from occupying those accidentally
        reserve_ports([config.libtorrent.port,
                       config.api.http_port,
                       config.api.https_port,
                       config.ipv8.port])

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

    async def start_components(self):
        self.logger.info("Session is using state directory: %s", self.config.state_dir)
        create_state_directory_structure(self.config.state_dir)
        patch_crypto_be_discovery()
        # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
        # certificates provided by the system trust store.
        if sys.platform == 'darwin':
            os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

        coros = [comp.start() for comp in self.components.values()]
        await gather(*coros, return_exceptions=not self.failfast)
        if self._startup_exception:
            self._reraise_startup_exception_in_separate_task()

    def start(self):
        """ This method returns session manager that will:
        1. Set the current session as a default on the enter the block nested in the with statement
        2. Call `await session._start() on the enter the block nested in the with statement
        3. Call `await session.shutdown() on the leave the block nested in the with statement

        Example of use:
            ...
            async with Session(tribler_config, components).start():
                # do work with the components
            ...
        """
        return session_manager(self)

    def _reraise_startup_exception_in_separate_task(self):
        async def exception_reraiser():
            # the exception should be intercepted by event loop exception handler
            raise self._startup_exception

        get_event_loop().create_task(exception_reraiser())

    def set_startup_exception(self, exc: Exception):
        if not self._startup_exception:
            self._startup_exception = exc

    async def shutdown(self):
        self.logger.info("Stopping components")
        await gather(*[create_task(component.stop()) for component in self.components.values()])
        self.logger.info("All components are stopped")

    def __enter__(self):
        Session._stack.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert Session._stack and Session._stack[-1] is self
        Session._stack.pop()


T = TypeVar('T', bound='Component')
