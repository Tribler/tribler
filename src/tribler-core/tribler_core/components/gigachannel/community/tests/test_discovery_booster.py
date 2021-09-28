import pytest

from tribler_core.components.gigachannel.community.discovery_booster import DiscoveryBooster

TEST_BOOSTER_TIMEOUT_IN_SEC = 10
TEST_BOOSTER_TAKE_STEP_INTERVAL_IN_SEC = 1


@pytest.fixture(name="booster")  # this workaround implemented only for pylint
def fixture_booster():
    class MockWalker:
        def __init__(self):
            self.take_step_called = False

        def take_step(self):
            self.take_step_called = True

    return DiscoveryBooster(
        timeout_in_sec=TEST_BOOSTER_TIMEOUT_IN_SEC,
        take_step_interval_in_sec=TEST_BOOSTER_TAKE_STEP_INTERVAL_IN_SEC,
        walker=MockWalker(),
    )


@pytest.fixture(name="community")  # this workaround implemented only for pylint
def fixture_community():
    class MockCommunity:
        def __init__(self):
            self.tasks = []

        def register_task(
            self, name, task, *args, delay=None, interval=None, ignore=()
        ):  # pylint: disable=unused-argument
            self.tasks.append(name)

        def cancel_pending_task(self, name):
            self.tasks.remove(name)

    return MockCommunity()


def test_init(booster):
    assert booster.timeout_in_sec == TEST_BOOSTER_TIMEOUT_IN_SEC
    assert booster.take_step_interval_in_sec == TEST_BOOSTER_TAKE_STEP_INTERVAL_IN_SEC

    assert booster.community is None
    assert booster.walker is not None


def test_apply(booster, community):
    booster.apply(None)
    assert booster.community is None

    booster.apply(community)
    assert booster.community == community
    assert booster.walker is not None

    assert len(community.tasks) == 2


def test_finish(booster, community):
    booster.apply(community)
    booster.finish()
    assert len(community.tasks) == 1


def test_take_step(booster):
    booster.take_step()
    assert booster.walker.take_step_called
