from __future__ import annotations

import logging
import os
import sys
from asyncio import Event, create_task, gather, get_event_loop
from pathlib import Path
from typing import Dict, List, Optional, Type, TypeVar

from tribler.core.components.component import Component, ComponentError, ComponentStartupException, \
    MultipleComponentsFound
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler.core.utilities.install_dir import get_lib_path
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.simpledefs import STATEDIR_CHANNELS_DIR, STATEDIR_DB_DIR


class SessionError(Exception):
    pass


class Session:
    _startup_exception: Optional[Exception] = None

    def __init__(self, config: TriblerConfig = None, components: List[Component] = (),
                 shutdown_event: Event = None, notifier: Notifier = None, failfast: bool = True):
        # deepcode ignore unguarded~next~call: not necessary to catch StopIteration on infinite iterator
        self.exit_code = None
        self.failfast = failfast
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config: TriblerConfig = config or TriblerConfig()
        self.shutdown_event: Event = shutdown_event or Event()
        self.notifier: Notifier = notifier or Notifier(loop=get_event_loop())
        self.components: Dict[Type[Component], Component] = {}
        for component in components:
            self.register(component.__class__, component)

        # Reserve various (possibly) fixed ports to prevent
        # components from occupying those accidentally
        reserve_ports([config.libtorrent.port,
                       config.api.http_port,
                       config.api.https_port,
                       config.ipv8.port])

    async def __aenter__(self):
        await self.start_components()
        return self

    async def __aexit__(self, *_):
        await self.shutdown()

    def get_instance(self, comp_cls: Type[T]) -> Optional[T]:
        # try to find a direct match
        if direct_match := self.components.get(comp_cls):
            return direct_match

        # try to find a subclass match
        candidates = {c for c in self.components if issubclass(c, comp_cls)}

        if not candidates:
            return None
        if len(candidates) >= 2:
            raise MultipleComponentsFound(comp_cls, candidates)

        candidate = candidates.pop()
        return self.components[candidate]

    def register(self, comp_cls: Type[Component], component: Component):
        if comp_cls in self.components:
            raise ComponentError(f'Component class {comp_cls.__name__} is already registered in session {self}')
        self.components[comp_cls] = component
        component.session = self

    async def start_components(self):
        self.logger.info('Start components...')
        self.logger.info(f'State directory: "{self.config.state_dir}"')
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

    def _reraise_startup_exception_in_separate_task(self):
        self.logger.info('Reraise startup exception in separate task')

        async def exception_reraiser():
            self.logger.info('Exception reraiser')

            e = self._startup_exception
            if isinstance(e, ComponentStartupException) and e.component.tribler_should_stop_on_component_error:
                self.logger.info('Shutdown with exit code 1')
                self.exit_code = 1
                self.shutdown_event.set()

            # the exception should be intercepted by event loop exception handler
            self.logger.info(f'Reraise startup exception: {self._startup_exception}')
            raise self._startup_exception

        get_event_loop().create_task(exception_reraiser())

    def set_startup_exception(self, exc: Exception):
        if not self._startup_exception:
            self._startup_exception = exc

    async def shutdown(self):
        self.logger.info("Stopping components")
        await gather(*[create_task(component.stop()) for component in self.components.values()])
        self.logger.info("All components are stopped")


T = TypeVar('T', bound='Component')


def create_state_directory_structure(state_dir: Path):
    """Create directory structure of the state directory."""
    state_dir.mkdir(exist_ok=True, parents=True)
    (state_dir / STATEDIR_DB_DIR).mkdir(exist_ok=True)
    (state_dir / STATEDIR_CHANNELS_DIR).mkdir(exist_ok=True)


def reserve_ports(ports_list: List[None, int]):
    for port in ports_list:
        if port is not None:
            default_network_utils.remember(port)
