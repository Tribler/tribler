from __future__ import annotations

import logging
import sys
from asyncio import Event
from typing import Optional, Set, TYPE_CHECKING, Type, Union

if TYPE_CHECKING:
    from tribler.core.components.session import Session, T


class ComponentError(Exception):
    pass


class ComponentStartupException(ComponentError):
    def __init__(self, component: Component, cause: Exception):
        super().__init__(component.__class__.__name__)
        self.component = component
        self.__cause__ = cause


class MissedDependency(ComponentError):
    def __init__(self, component: Component, dependency: Type[Component]):
        msg = f'Missed dependency: {component.__class__.__name__} requires {dependency.__name__} to be active'
        super().__init__(msg)
        self.component = component
        self.dependency = dependency


class MultipleComponentsFound(ComponentError):
    def __init__(self, comp_cls: Type[Component], candidates: Set[Component]):
        msg = f'Found multiple subclasses for the class {comp_cls}. Candidates are: {candidates}.'
        super().__init__(msg)


class NoneComponent:
    def __getattr__(self, item):
        return NoneComponent()


class Component:
    tribler_should_stop_on_component_error = True

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
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

    async def start(self):
        self.logger.info(f'Start: {self.__class__.__name__}')
        try:
            await self.run()
        except Exception as e:  # pylint: disable=broad-except
            # Writing to stderr is for the case when logger is not configured properly (as my happen in local tests,
            # for example) to avoid silent suppression of the important exceptions
            sys.stderr.write(f'\nException in {self.__class__.__name__}.start(): {type(e).__name__}:{e}\n')
            if isinstance(e, MissedDependency):
                # Use logger.error instead of logger.exception here to not spam log with multiple error tracebacks
                self.logger.error(e)
            else:
                self.logger.exception(f'Exception in {self.__class__.__name__}.start(): {type(e).__name__}:{e}')
            self.failed = True
            self.started_event.set()
            if self.session.failfast:
                raise e
            self.session.set_startup_exception(ComponentStartupException(self, e))
        self.started_event.set()

    async def stop(self):
        component_name = self.__class__.__name__
        dependants = sorted(component.__class__.__name__ for component in self.reverse_dependencies)
        self.logger.info(f'Stopping {component_name}: waiting for {dependants} to release it')
        await self.unused_event.wait()
        self.logger.info(f"Component {component_name} free, shutting down")
        try:
            await self.shutdown()
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(f"Exception in {self.__class__.__name__}.shutdown(): {type(e).__name__}:{e}")
            raise
        finally:
            self.stopped = True
            for dep in list(self.dependencies):
                self._release_instance(dep)
            remaining_components = sorted(
                c.__class__.__name__ for c in self.session.components.values() if not c.stopped)
            self.logger.info(f"Component {component_name}, stopped. Remaining components: {remaining_components}")

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

        await dep.started_event.wait()
        if dep.failed:
            self.logger.warning(f'Component {self.__class__.__name__} has failed dependency {dependency.__name__}')
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
