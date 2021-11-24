from unittest.mock import MagicMock

import pytest

from tribler_common.reported_error import ReportedError

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import NoneComponent, Session
from tribler_core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tag.tag_component import TagComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access, not-callable, redefined-outer-name

async def test_rest_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), Ipv8Component(), LibtorrentComponent(), ResourceMonitorComponent(),
                  BandwidthAccountingComponent(), GigaChannelComponent(), TagComponent(), SocksServersComponent(),
                  MetadataStoreComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        # Test REST component starts normally
        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager

        # Test report callback works
        # mock callbacks
        comp._events_endpoint.on_tribler_exception = MagicMock()

        # try to call report_callback from core_exception_handler and assert
        # that corresponding methods in events_endpoint and state_endpoint have been called

        error = ReportedError(type='', text='text', event={})
        comp._core_exception_handler.report_callback(error)
        comp._events_endpoint.on_tribler_exception.assert_called_with(error)

        await session.shutdown()


@pytest.fixture
def endpoint_cls():
    class Endpoint(RESTEndpoint):
        ...

    return Endpoint


@pytest.fixture
def rest_component():
    component = RESTComponent()
    component.root_endpoint = MagicMock()
    return component


async def test_maybe_add_check_args(rest_component, endpoint_cls):
    # test that in case `*args` in `maybe_add` function contains `NoneComponent` instance
    # no root_endpoint methods are called
    rest_component.maybe_add('path', endpoint_cls, NoneComponent())
    rest_component.root_endpoint.assert_not_called()

    rest_component.maybe_add('path', endpoint_cls, NoneComponent(), 'some arg')
    rest_component.root_endpoint.assert_not_called()


async def test_maybe_add_check_kwargs(rest_component, endpoint_cls):
    # test that in case `**kwargs` in `maybe_add` function contains `NoneComponent` instance
    # no root_endpoint methods are called
    rest_component.maybe_add('path', endpoint_cls, component=NoneComponent())
    rest_component.root_endpoint.assert_not_called()

    rest_component.maybe_add('path', endpoint_cls, component=NoneComponent(), another='kwarg')
    rest_component.root_endpoint.assert_not_called()


async def test_maybe_add(rest_component, endpoint_cls):
    # test that in case there are no `NoneComponent` instances in `**kwargs` or `*args`
    # root_endpoint methods are called
    rest_component.maybe_add('path', endpoint_cls, 'arg')
    rest_component.root_endpoint.asert_called_once()
