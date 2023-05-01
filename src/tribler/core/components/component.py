from __future__ import annotations

import logging
import sys
import time
from asyncio import Event
from typing import Optional, Set, TYPE_CHECKING, Type, Union

from tribler.core.components.exceptions import ComponentStartupException, MissedDependency, NoneComponent
from tribler.core.components.reporter.exception_handler import default_core_exception_handler
from tribler.core.sentry_reporter.sentry_reporter import SentryReporter

if TYPE_CHECKING:
    from tribler.core.components.session import Session, T


class Component:
    tribler_should_stop_on_component_error = True

    def __init__(self, reporter: Optional[SentryReporter] = None):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        self.logger.info('__init__')
        self.session: Optional[Session] = None
        self.dependencies: Set[Component] = set()
        self.reverse_dependencies: Set[Component] = set()
        self.started_event = Event()
        self.failed = False
        self.unused_event = Event()
        self.stopped = False
        # Every component starts unused, so it does not lock the whole system on shutdown
        self.unused_event.set()
        self.reporter = reporter or default_core_exception_handler.sentry_reporter

    async def start(self):
        start_time = time.time()
        self._set_component_status('starting...')
        try:
            await self.run()
            self._set_component_status(f'started in {time.time() - start_time:.4f}s')
        except Exception as e:  # pylint: disable=broad-except
            # Writing to stderr is for the case when logger is not configured properly (as my happen in local tests,
            # for example) to avoid silent suppression of the important exceptions
            sys.stderr.write(f'\nException in {self.name}.start(): {type(e).__name__}:{e}\n')
            msg = f'exception in {self.name}.start(): {type(e).__name__}:{e}'
            exc_info = not isinstance(e, MissedDependency)
            self._set_component_status(msg, logging.ERROR, exc_info=exc_info)
            self.failed = True
            self.started_event.set()
            if self.session.failfast:
                raise e
            self.session.set_startup_exception(ComponentStartupException(self, e))
        self.started_event.set()

    async def stop(self):
        dependants = sorted(component.__class__.__name__ for component in self.reverse_dependencies)
        msg = f'Stopping {self.name}: waiting for {dependants} to release it'
        self._set_component_status(msg)
        await self.unused_event.wait()
        self._set_component_status('shutting down')
        try:
            await self.shutdown()
            self._set_component_status('shut down')
        except Exception as e:  # pylint: disable=broad-except
            msg = f"exception in {self.name}.shutdown(): {type(e).__name__}:{e}"
            self._set_component_status(msg, logging.ERROR, exc_info=True)
            raise
        finally:
            self.stopped = True
            for dep in list(self.dependencies):
                self._release_instance(dep)
            remaining_components = sorted(
                c.__class__.__name__ for c in self.session.components.values() if not c.stopped)
            self.logger.info(f"Component {self.name}, stopped. Remaining components: {remaining_components}")

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
            raise MissedDependency(self, dependency)
        return dep

    async def get_component(self, dependency: Type[T]) -> Optional[T]:
        """ Resolve the dependency to a component.
        The method will wait the component to be initialised.

        Returns:    The component instance.
                    In case of a missed or failed dependency None will be returned.
        """
        dep = self.session.get_instance(dependency)
        if not dep:
            return None

        self._set_component_status(f'waiting for {dep.name}')
        await dep.started_event.wait()

        if dep.failed:
            self.logger.warning(f'Component {self.name} has failed dependency {dependency.__name__}')
            return None

        if dep not in self.dependencies and dep is not self:
            self.dependencies.add(dep)
            dep._use_by(self)  # pylint: disable=protected-access

        return dep

    async def maybe_component(self, dependency: Type[T]) -> Union[T, NoneComponent]:
        """ This method returns instance of the dependency in case this instance can be created
        otherwise it returns instance of NoneComponent class

        Example of using:

        libtorrent_component = await self.maybe_component(LibtorrentComponent)
        print(libtorrent_component.download_manager.libtorrent_port) # No NPE exception
        """
        return await self.get_component(dependency) or NoneComponent()

    def release_component(self, dependency: Type[T]):
        dep = self.session.get_instance(dependency)
        if dep:
            self._release_instance(dep)

    def _release_instance(self, dep: Component):
        if dep in self.dependencies:
            self.dependencies.discard(dep)
            dep._unuse_by(self)  # pylint: disable=protected-access

    def _use_by(self, component: Component):
        assert component not in self.reverse_dependencies
        self.reverse_dependencies.add(component)
        if len(self.reverse_dependencies) == 1:
            self.unused_event.clear()

    def _unuse_by(self, component: Component):
        assert component in self.reverse_dependencies
        self.reverse_dependencies.remove(component)
        if not self.reverse_dependencies:
            self.unused_event.set()

    def _set_component_status(self, status: str, log_level: int = logging.INFO, **kwargs):
        self.reporter.additional_information['components_status'][self.name] = status
        self.logger.log(log_level, f'{self.name}: {status}', **kwargs)
