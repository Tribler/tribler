from unittest.mock import patch

import pytest

from tribler.core.components.component import Component
from tribler.core.components.exceptions import MissedDependency, MultipleComponentsFound, NoneComponent
from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.db_corruption_handling.base import DatabaseIsCorrupted


class ComponentTestException(Exception):
    pass


async def test_session_start_shutdown(tribler_config):
    class TestComponent(Component):
        def __init__(self):
            self.run_was_executed = self.shutdown_was_executed = False
            super().__init__()

        async def run(self):
            self.run_was_executed = True

        async def shutdown(self):
            self.shutdown_was_executed = True

    class TestComponentA(TestComponent):
        pass

    class TestComponentB(TestComponent):
        pass

    session = Session(tribler_config, [TestComponentA(), TestComponentB()])
    async with session:
        a = session.get_instance(TestComponentA)
        b = session.get_instance(TestComponentB)

        for component in a, b:
            assert component.run_was_executed
            assert component.started_event.is_set()
            assert not component.shutdown_was_executed
            assert not component.stopped

    for component in a, b:
        assert component.run_was_executed
        assert component.started_event.is_set()
        assert component.shutdown_was_executed
        assert component.stopped


@patch('tribler.core.components.component.get_global_process_manager')
async def test_session_start_database_corruption_detected(get_global_process_manager):
    exception = DatabaseIsCorrupted('db_path_string')

    class TestComponent(Component):
        async def run(self):
            raise exception

    component = TestComponent()

    await component.start()
    get_global_process_manager().sys_exit.assert_called_once_with(99, exception)


class ComponentA(Component):
    pass


class RequireA(Component):
    async def run(self):
        await self.require_component(ComponentA)


class ComponentB(Component):
    pass


class DerivedB(ComponentB):
    pass


async def test_required_dependency(tribler_config):
    session = Session(tribler_config, [ComponentA(), RequireA()])
    async with session:
        a = session.get_instance(ComponentA)
        b = session.get_instance(RequireA)

        assert a in b.dependencies and not b.reverse_dependencies
        assert not a.dependencies and b in a.reverse_dependencies
        assert b.unused_event.is_set() and not a.unused_event.is_set()

    for component in a, b:
        assert not component.dependencies and not component.reverse_dependencies
        assert component.unused_event.is_set()


async def test_required_dependency_missed(tribler_config):
    session = Session(tribler_config, [RequireA()])
    with pytest.raises(MissedDependency, match='^Missed dependency: RequireA requires ComponentA to be active$'):
        await session.start_components()


async def test_required_dependency_missed_failfast(tribler_config):
    session = Session(tribler_config, [RequireA()], failfast=False)
    async with session:
        await session.start_components()
        b = session.get_instance(RequireA)
        assert b
        assert b.started_event.is_set()
        assert b.failed


async def test_component_shutdown_failure(tribler_config):
    class RequireAWithException(RequireA):
        async def shutdown(self):
            raise ComponentTestException

    session = Session(tribler_config, [ComponentA(), RequireAWithException()])
    a = session.get_instance(ComponentA)
    b = session.get_instance(RequireAWithException)

    await session.start_components()

    assert not a.unused_event.is_set()

    with pytest.raises(ComponentTestException):
        await session.shutdown()

    for component in a, b:
        assert not component.dependencies
        assert not component.reverse_dependencies
        assert component.unused_event.is_set()
        assert component.stopped


async def test_maybe_component(tribler_config):  # pylint: disable=unused-argument
    session = Session(tribler_config, [ComponentA()])
    async with session:
        component_a = await session.get_instance(ComponentA).maybe_component(ComponentA)
        component_b = await session.get_instance(ComponentA).maybe_component(ComponentB)

        assert isinstance(component_a, ComponentA)
        assert isinstance(component_b, NoneComponent)
        assert isinstance(component_b.any_attribute, NoneComponent)
        assert isinstance(component_b.any_attribute.any_nested_attribute, NoneComponent)


def test_get_instance_direct_match(tribler_config: TriblerConfig):
    session = Session(tribler_config, [ComponentA(), ComponentB(), DerivedB()])
    assert isinstance(session.get_instance(ComponentB), ComponentB)


def test_get_instance_subclass_match(tribler_config: TriblerConfig):
    session = Session(tribler_config, [ComponentA(), DerivedB()])
    assert isinstance(session.get_instance(ComponentB), DerivedB)


def test_get_instance_no_match(tribler_config: TriblerConfig):
    session = Session(tribler_config, [ComponentA()])
    assert not session.get_instance(ComponentB)


def test_get_instance_two_subclasses_match(tribler_config: TriblerConfig):
    class SecondDerivedB(ComponentB):
        pass

    session = Session(tribler_config, [ComponentA(), DerivedB(), SecondDerivedB()])
    with pytest.raises(MultipleComponentsFound):
        session.get_instance(ComponentB)
