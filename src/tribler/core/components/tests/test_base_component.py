import pytest

from tribler.core.components.base import Component, MissedDependency, NoneComponent
from tribler.core.components.session import Session


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

    class ComponentA(TestComponent):
        pass

    class ComponentB(TestComponent):
        pass

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    async with session:
        a = session.get_instance(ComponentA)
        b = session.get_instance(ComponentB)

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


async def test_required_dependency(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    async with session:
        a = session.get_instance(ComponentA)
        b = session.get_instance(ComponentB)

        assert a in b.dependencies and not b.reverse_dependencies
        assert not a.dependencies and b in a.reverse_dependencies
        assert b.unused_event.is_set() and not a.unused_event.is_set()

    for component in a, b:
        assert not component.dependencies and not component.reverse_dependencies
        assert component.unused_event.is_set()


async def test_required_dependency_missed(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

    session = Session(tribler_config, [ComponentB()])
    with pytest.raises(MissedDependency, match='^Missed dependency: ComponentB requires ComponentA to be active$'):
        await session.start_components()


async def test_required_dependency_missed_failfast(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

    session = Session(tribler_config, [ComponentB()], failfast=False)
    async with session:
        await session.start_components()
        b = session.get_instance(ComponentB)
        assert b
        assert b.started_event.is_set()
        assert b.failed


async def test_component_shutdown_failure(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

        async def shutdown(self):
            raise ComponentTestException

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    a = session.get_instance(ComponentA)
    b = session.get_instance(ComponentB)

    await session.start_components()

    assert not a.unused_event.is_set()

    with pytest.raises(ComponentTestException):
        await session.shutdown()

    for component in a, b:
        assert not component.dependencies
        assert not component.reverse_dependencies
        assert component.unused_event.is_set()
        assert component.stopped


async def test_maybe_component(loop, tribler_config):  # pylint: disable=unused-argument
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        pass

    session = Session(tribler_config, [ComponentA()])
    async with session:
        component_a = await session.get_instance(ComponentA).maybe_component(ComponentA)
        component_b = await session.get_instance(ComponentA).maybe_component(ComponentB)

        assert isinstance(component_a, ComponentA)
        assert isinstance(component_b, NoneComponent)
        assert isinstance(component_b.any_attribute, NoneComponent)
        assert isinstance(component_b.any_attribute.any_nested_attribute, NoneComponent)
