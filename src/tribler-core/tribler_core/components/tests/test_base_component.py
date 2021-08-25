import re

from typing import List, Type
from tribler_core.components.base import Component, ComponentError, Session, T
from tribler_core.config.tribler_config import TriblerConfig

import pytest


def make_test_components():
    class TestComponent(Component):
        run_was_executed = False
        shutdown_was_executed = False
        should_be_enabled_result_value = True
        default_implementation: T

        @classmethod
        def should_be_enabled(cls, config: TriblerConfig):
            return cls.should_be_enabled_result_value

        @classmethod
        def make_implementation(cls: Type[T], config, enable) -> T:
            result = cls.default_implementation(cls)
            result.enabled = enable
            return result

        async def run(self):
            self.run_was_executed = True

        async def shutdown(self):
            self.shutdown_was_executed = True


    class ComponentA(TestComponent):
        pass

    class ComponentB(TestComponent):
        pass

    class ComponentAImp(ComponentA):
        pass

    class ComponentBImp(ComponentB):
        pass

    ComponentA.default_implementation = ComponentAImp
    ComponentB.default_implementation = ComponentBImp

    return ComponentA, ComponentB


def components_gen(config: TriblerConfig, component_list: List[T]):
    for cls in component_list:
        yield cls.make_implementation(config, cls.should_be_enabled(config))


async def test_session_start_shutdown(loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentA, ComponentB])))
    with session:
        a = ComponentA.imp()
        b = ComponentB.imp()

        assert a.enabled and not a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert b.enabled and not b.run_was_executed and not b.shutdown_was_executed and not b.stopped
        assert not a.started.is_set() and not b.started.is_set()

        await session.start()

        a2 = ComponentA.imp()
        b2 = ComponentB.imp()
        assert a2 is a and b2 is b

        assert a.enabled and a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert b.enabled and b.run_was_executed and not b.shutdown_was_executed and not b.stopped
        assert a.started.is_set() and b.started.is_set()

        session.shutdown_event.set()
        await session.shutdown()

        a3 = ComponentA.imp()
        b3 = ComponentB.imp()
        assert a3 is a and b3 is b

        assert a.enabled and a.run_was_executed and a.shutdown_was_executed and a.stopped
        assert b.enabled and b.run_was_executed and b.shutdown_was_executed and b.stopped
        assert a.started.is_set() and b.started.is_set()


async def test_disabled_component(loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()
    ComponentA.should_be_enabled_result_value = False

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentA, ComponentB])))
    with session:
        a = ComponentA.imp()
        b = ComponentB.imp()

        assert not a.enabled and not a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert b.enabled and not b.run_was_executed and not b.shutdown_was_executed and not b.stopped
        assert not a.started.is_set() and not b.started.is_set()

        await session.start()

        a2 = ComponentA.imp()
        b2 = ComponentB.imp()
        assert a2 is a and b2 is b

        assert not a.enabled and a.run_was_executed and not a.shutdown_was_executed and not a.stopped
        assert b.enabled and b.run_was_executed and not b.shutdown_was_executed and not b.stopped
        assert a.started.is_set() and b.started.is_set()

        session.shutdown_event.set()
        await session.shutdown()

        a3 = ComponentA.imp()
        b3 = ComponentB.imp()
        assert a3 is a and b3 is b

        assert not a.enabled and a.run_was_executed and a.shutdown_was_executed and a.stopped
        assert b.enabled and b.run_was_executed and b.shutdown_was_executed and b.stopped
        assert a.started.is_set() and b.started.is_set()


async def test_required_dependency_enabled(loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()
    ComponentB.run = lambda self: self.use(ComponentA)

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentA, ComponentB])))
    with session:
        a = ComponentA.imp()
        b = ComponentB.imp()

        assert a.enabled and b.enabled
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


async def test_required_dependency_disabled(loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()
    ComponentA.should_be_enabled_result_value = False
    ComponentB.run = lambda self: self.use(ComponentA)

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentA, ComponentB])))
    with session:
        a = ComponentA.imp()
        b = ComponentB.imp()

        assert not a.enabled and b.enabled
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


async def test_required_dependency_missed(capsys, loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()
    ComponentB.run = lambda self: self.use(ComponentA)

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentB])))
    with session:
        with pytest.raises(ComponentError, match=r'ComponentA implementation not found in <Session:\d+>'):
            ComponentA.imp()

        b = ComponentB.imp()
        assert not b.components_used_by_me

        with pytest.raises(ComponentError, match=r'ComponentA implementation not found in <Session:\d+>'):
            await session.start()

        captured = capsys.readouterr()
        assert re.match(r'\nException in ComponentBImp.start\(\): '
                        r'ComponentError:ComponentA implementation not found in <Session:\d+>\n', captured.err)


async def test_optional_dependency_missed(loop, tribler_config):  # pylint: disable=unused-argument
    ComponentA, ComponentB = make_test_components()
    ComponentB.run = lambda self: self.use(ComponentA, required=False)

    session = Session(tribler_config, list(components_gen(tribler_config, [ComponentB])))
    with session:
        with pytest.raises(ComponentError, match=r'ComponentA implementation not found in <Session:\d+>'):
            ComponentA.imp()

        b = ComponentB.imp()
        assert not b.components_used_by_me

        await session.start()

        a = ComponentA.imp()
        assert not a.enabled  # A mock version of the component A presents, but it is not marked as enabled

        assert a.started.is_set() and b.started.is_set()
        assert a in b.components_used_by_me
        assert b in a.in_use_by

        session.shutdown_event.set()
        await session.shutdown()

        assert a.started.is_set() and b.started.is_set()
        assert a.stopped and b.stopped
        assert not b.components_used_by_me and not a.in_use_by
