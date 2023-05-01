from __future__ import annotations

from typing import Set, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from tribler.core.components.component import Component


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
