from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.restapi.rest_manager import RESTManager


class RESTComponent(Component):
    enable_in_gui_test_mode = True

    rest_manager: RESTManager


@testcomponent
class RESTComponentMock(RESTComponent):
    rest_manager = Mock()
