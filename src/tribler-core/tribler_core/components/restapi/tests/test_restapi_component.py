from unittest.mock import MagicMock

import pytest

from tribler_common.reported_error import ReportedError

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.reporter.exception_handler import CoreExceptionHandler
from tribler_core.components.restapi.restapi_component import RESTComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access, not-callable

def assert_report_callback_is_correct(component: RESTComponent):
    assert CoreExceptionHandler.report_callback
    component._events_endpoint.on_tribler_exception = MagicMock()
    component._state_endpoint.on_tribler_exception = MagicMock()

    error = ReportedError(type='', text='text', event={})
    CoreExceptionHandler.report_callback(error)

    component._events_endpoint.on_tribler_exception.assert_called_with(error)
    component._state_endpoint.on_tribler_exception.assert_called_with(error.text)


async def test_restful_component(tribler_config):
    components = [KeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager
        assert_report_callback_is_correct(comp)
        await session.shutdown()
