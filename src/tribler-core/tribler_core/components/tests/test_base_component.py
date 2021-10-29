import pytest

from tribler_core.components.base import Component, MissedDependency, Session, SessionError

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
            assert not component.started_event.is_set()
            assert not component.shutdown_was_executed
            assert not component.stopped

        await session.start()

        assert ComponentA.instance() is a and ComponentB.instance() is b
        for component in a, b:
            assert component.run_was_executed
            assert component.started_event.is_set()
            assert not component.shutdown_was_executed
            assert not component.stopped

        session.shutdown_event.set()
        await session.shutdown()

        assert ComponentA.instance() is a and ComponentB.instance() is b
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
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        for component in a, b:
            assert not component.dependencies and not component.reverse_dependencies
            assert component.unused_event.is_set()

        await session.start()

        assert a in b.dependencies and not b.reverse_dependencies
        assert not a.dependencies and b in a.reverse_dependencies
        assert b.unused_event.is_set() and not a.unused_event.is_set()

        session.shutdown_event.set()
        await session.shutdown()

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
    with session:
        assert ComponentA.instance() is None
        b = ComponentB.instance()

        with pytest.raises(MissedDependency, match='^Missed dependency: ComponentB requires ComponentA to be active$'):
            await session.start()

    session = Session(tribler_config, [ComponentB()], failfast=False)
    with session:
        b = ComponentB.instance()

        await session.start()

        assert ComponentB.instance() is b
        assert b.started_event.is_set()
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

        assert not a.unused_event.is_set()

        with pytest.raises(TestException):
            await session.shutdown()

        for component in a, b:
            assert not component.dependencies
            assert not component.reverse_dependencies
            assert component.unused_event.is_set()
            assert component.stopped


def test_session_context_manager(loop, tribler_config):   # pylint: disable=unused-argument
    session1 = Session(tribler_config, [])
    session2 = Session(tribler_config, [])
    session3 = Session(tribler_config, [])

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()

    session1.set_as_default()
    assert Session.current() is session1

    with session2:
        assert Session.current() is session2
        with session3:
            assert Session.current() is session3
        assert Session.current() is session2
    assert Session.current() is session1

    Session.unset_default_session()

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()
