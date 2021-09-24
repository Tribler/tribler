import pytest

from tribler_core.components.base import Component, ComponentError, Session, T


def make_test_components():
    class TestComponent(Component):
        run_was_executed = False
        shutdown_was_executed = False
        should_be_enabled_result_value = True
        default_implementation: T

        async def run(self):
            self.run_was_executed = True

        async def shutdown(self):
            self.shutdown_was_executed = True

    class ComponentA(TestComponent):
        pass

    class ComponentB(TestComponent):
        pass

    return ComponentA, ComponentB


async def test_session_start_shutdown(tribler_config):
    ComponentA, ComponentB = make_test_components()
    session = Session(tribler_config, [ComponentA(), ComponentB()])
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        assert not a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert not b.run_was_executed and not b.shutdown_was_executed and not b.stopped

        assert not a.started.is_set() and not b.started.is_set()

        await session.start()

        a2 = ComponentA.instance()
        b2 = ComponentB.instance()
        assert a2 is a and b2 is b

        assert a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert b.run_was_executed and not b.shutdown_was_executed and not b.stopped
        assert a.started.is_set() and b.started.is_set()

        session.shutdown_event.set()
        await session.shutdown()

        a3 = ComponentA.instance()
        b3 = ComponentB.instance()
        assert a3 is a and b3 is b

        assert a.run_was_executed and a.shutdown_was_executed and a.stopped
        assert b.run_was_executed and b.shutdown_was_executed and b.stopped
        assert a.started.is_set() and b.started.is_set()


async def test_required_dependency_enabled(tribler_config):
    ComponentA, ComponentB = make_test_components()
    ComponentB.run = lambda self: self.get_component(ComponentA)

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        assert not a.started.is_set() and not b.started.is_set()
        assert not b.components_used_by_me and not a.in_use_by

        await session.start()

        assert a.started.is_set() and b.started.is_set()
        assert a in b.components_used_by_me
        assert b in a.in_use_by

        session.shutdown_event.set()
        await session.shutdown()

        assert a.started.is_set() and b.started.is_set()
        assert a.stopped and b.stopped
        assert not b.components_used_by_me and not a.in_use_by


async def test_required_dependency_disabled(tribler_config):
    ComponentA, ComponentB = make_test_components()
    ComponentB.run = lambda self: self.get_component(ComponentA)

    session = Session(tribler_config, [ComponentA(), ComponentB()])
    with session:
        a = ComponentA.instance()
        b = ComponentB.instance()

        assert not a.started.is_set() and not b.started.is_set()
        assert not b.components_used_by_me and not a.in_use_by

        await session.start()

        assert a.started.is_set() and b.started.is_set()
        assert a in b.components_used_by_me
        assert b in a.in_use_by

        session.shutdown_event.set()
        await session.shutdown()

        assert a.started.is_set() and b.started.is_set()
        assert a.stopped and b.stopped
        assert not b.components_used_by_me and not a.in_use_by


async def test_dependency_missed(tribler_config):
    ComponentA, ComponentB = make_test_components()

    async def run(self):
        await self.require_component(ComponentA)

    ComponentB.run = run

    session = Session(tribler_config, [ComponentB()])
    with session:
        assert not ComponentA.instance()

        b = ComponentB.instance()
        assert not b.components_used_by_me
        with pytest.raises(ComponentError):
            await session.start()
