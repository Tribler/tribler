import pytest

from tribler_core.components.base import Component, ComponentError, Session, T

pytestmark = pytest.mark.asyncio


class TestException(Exception):
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
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        for component in a, b:
            assert not component.run_was_executed
            assert not component.started.is_set()
            assert not component.shutdown_was_executed
            assert not component.stopped

        await session.start()

        assert ComponentA.instance() is a and ComponentB.instance() is b
        for component in a, b:
            assert component.run_was_executed
            assert component.started.is_set()
            assert not component.shutdown_was_executed
            assert not component.stopped

        session.shutdown_event.set()
        await session.shutdown()

        assert ComponentA.instance() is a and ComponentB.instance() is b
        for component in a, b:
            assert component.run_was_executed
            assert component.started.is_set()
            assert component.shutdown_was_executed
            assert component.stopped


async def test_required_dependency(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        for component in a, b:
            assert not component.dependencies and not component.reverse_dependencies

        await session.start()

        assert a in b.dependencies and not b.reverse_dependencies
        assert not a.dependencies and b in a.reverse_dependencies

        session.shutdown_event.set()
        await session.shutdown()

        for component in a, b:
            assert not component.dependencies and not component.reverse_dependencies


async def test_required_dependency_missed(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

    session = Session(tribler_config, [ComponentB()])
    with session:
        assert ComponentA.instance() is None
        b = ComponentB.instance()

        with pytest.raises(ComponentError, match='^Missed dependency: ComponentB requires ComponentA to be active$'):
            await session.start()  # failfast == True

    session = Session(tribler_config, [ComponentB()])
    with session:
        b = ComponentB.instance()

        await session.start(failfast=False)

        assert ComponentB.instance() is b
        assert b.started.is_set()
        assert b.failed


async def test_component_shutdown_failure(tribler_config):
    class ComponentA(Component):
        pass

    class ComponentB(Component):
        async def run(self):
            await self.require_component(ComponentA)

        async def shutdown(self):
            raise TestException

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        await session.start()

        with pytest.raises(TestException):
            await session.shutdown()

        for component in a, b:
            assert not component.dependencies
            assert not component.reverse_dependencies
            assert component.unused.is_set()
            assert component.stopped
