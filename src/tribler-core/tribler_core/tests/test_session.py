import asyncio
import shutil
from asyncio import get_event_loop, sleep
from unittest.mock import Mock

from _socket import getaddrinfo

from ipv8.util import succeed

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.config.tests.test_tribler_config import CONFIG_PATH
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.session import IGNORED_ERRORS, Session
from tribler_core.tests.tools.base_test import MockObject

# Pylint does not agree with the way pytest handles fixtures.
# pylint: disable=W0613,W0621


@pytest.fixture
def mocked_endpoints(session):
    session.api_manager = MockObject()
    session.api_manager.stop = lambda: succeed(None)
    session.api_manager.set_ipv8_session = lambda _: None
    mocked_endpoints = {}

    def get_endpoint_mock(name):
        if name in mocked_endpoints:
            return mocked_endpoints[name]
        endpoint = Mock()
        mocked_endpoints[name] = endpoint
        return endpoint

    session.api_manager.get_endpoint = get_endpoint_mock


def test_unhandled_error_observer(mocked_endpoints, session):
    """
    Test the unhandled error observer
    """
    mock_events = Mock()
    mock_state = Mock()
    session.api_manager.get_endpoint('events').on_tribler_exception = mock_events
    session.api_manager.get_endpoint('state').on_tribler_exception = mock_state

    # This indirect method of raising exceptions is necessary
    # to circumvent the test runner catching exceptions by itself
    def function_that_triggers_exception():
        raise Exception("foobar")

    get_event_loop().call_soon(function_that_triggers_exception)
    get_event_loop()._run_once()
    for m in [mock_state, mock_events]:
        assert "function_that_triggers_exception" in m.call_args[0][0]
        assert "foobar" in m.call_args[0][0]


@pytest.mark.asyncio
async def test_error_observer_ignored_error(mocked_endpoints, session):
    """
    Testing whether some errors are ignored (like socket errors)
    """
    session.api_manager.get_endpoint('events').on_tribler_exception = Mock()
    session.api_manager.get_endpoint('state').on_tribler_exception = Mock()

    def generate_exception_on_reactor(exception):
        def gen_except():
            raise exception

        get_event_loop().call_soon(gen_except)

    exceptions_list = [(exc[0](exc[1], "exc message") if isinstance(exc, tuple) else exc(123, "exc message"))
                       for exc in IGNORED_ERRORS]

    exceptions_list.append(RuntimeError(0, "invalid info-hash"))

    for exception in exceptions_list:
        generate_exception_on_reactor(exception)

    # Even though we could have used _run_once instead of a sleep, it seems that _run_once does not always
    # immediately clean the reactor, leading to a possibility that the test starts to shut down before the exception
    # is raised.
    await sleep(0.05)

    session.api_manager.get_endpoint('state').on_tribler_exception.assert_not_called()
    session.api_manager.get_endpoint('events').on_tribler_exception.assert_not_called()

    # This is a "canary" to test that we can handle true exceptions
    get_event_loop().call_soon(getaddrinfo, "dfdfddfd23424fdfdf", 2323)

    await sleep(0.05)

    session.api_manager.get_endpoint('state').on_tribler_exception.assert_not_called()
    session.api_manager.get_endpoint('events').on_tribler_exception.assert_not_called()

    # This is a "canary" to test to catch false negative tests
    def real_raise():
        raise Exception()

    get_event_loop().call_soon(real_raise)
    await sleep(0.05)
    session.api_manager.get_endpoint('state').on_tribler_exception.assert_called_once()
    session.api_manager.get_endpoint('events').on_tribler_exception.assert_called_once()


@pytest.mark.asyncio
async def test_load_ipv8_overlays(mocked_endpoints, enable_ipv8, session):
    """
    Test whether non-testnet communities are loaded, if configured to do so.
    """
    session.config.trustchain.testnet = False
    session.config.tunnel_community.testnet = False
    session.config.chant.testnet = False
    session.config.dht.enabled = True
    session.config.tunnel_community.enabled = True
    session.config.popularity_community.enabled = True
    session.config.chant.enabled = True

    await session.start()

    loaded_launchers = [overlay.__class__.__name__ for overlay in session.ipv8.overlays]
    assert "DHTDiscoveryCommunity" in loaded_launchers
    assert "TriblerTunnelCommunity" in loaded_launchers
    assert "TriblerTunnelTestnetCommunity" not in loaded_launchers
    assert "PopularityCommunity" in loaded_launchers
    assert "GigaChannelCommunity" in loaded_launchers
    assert "GigaChannelTestnetCommunity" not in loaded_launchers


@pytest.mark.asyncio
async def test_load_ipv8_overlays_testnet(mocked_endpoints, enable_ipv8, session):
    """
    Test whether testnet communities are loaded, if configured to do so.
    """
    session.config.trustchain.testnet = True
    session.config.bandwidth_accounting.testnet = True
    session.config.tunnel_community.testnet = True
    session.config.chant.testnet = True
    session.config.dht.enabled = True
    session.config.tunnel_community.enabled = True
    session.config.popularity_community.enabled = True
    session.config.chant.enabled = True

    await session.start()

    loaded_launchers = [overlay.__class__.__name__ for overlay in session.ipv8.overlays]
    assert "BandwidthAccountingCommunity" not in loaded_launchers
    assert "BandwidthAccountingTestnetCommunity" in loaded_launchers
    assert "DHTDiscoveryCommunity" in loaded_launchers
    assert "TriblerTunnelCommunity" not in loaded_launchers
    assert "TriblerTunnelTestnetCommunity" in loaded_launchers
    assert "PopularityCommunity" in loaded_launchers
    assert "GigaChannelCommunity" not in loaded_launchers
    assert "GigaChannelTestnetCommunity" in loaded_launchers


@pytest.mark.asyncio
async def test_config_error_notification(tmpdir):
    """
    Test if config error is notified on session startup.
    """

    # 1. Setup corrupted config
    shutil.copy2(CONFIG_PATH / 'corrupt-triblerd.conf', tmpdir / 'triblerd.conf')

    tribler_config = TriblerConfig.load(file=tmpdir / 'triblerd.conf', state_dir=tmpdir, reset_config_on_error=True)

    # 2. Initialize session with corrupted config, disable upgrader for simplicity.
    # By mocking the notifier, we can check if the notify was called with correct parameters
    session = Session(tribler_config)
    session.upgrader_enabled = False
    session.notifier = Mock()

    # 3. Start the session which should internally call the notifier.
    await session.start()
    # Notifier uses asyncio loop internally, so we must wait at least a single loop cycle
    await asyncio.sleep(0)

    # 4. There could be multiple notify calls but we are only interested in the config error
    # so using 'assert_any_call' here to check if the notify was called.
    session.notifier.notify.assert_any_call(NTFY.REPORT_CONFIG_ERROR, tribler_config.error)

    # 5. Always shutdown the session at the end.
    await session.shutdown()
