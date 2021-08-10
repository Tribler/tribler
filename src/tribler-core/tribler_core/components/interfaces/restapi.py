from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.restapi.rest_manager import RESTManager


class RESTComponent(Component):
    core = True

    rest_manager: RESTManager

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.api.http_enabled or config.api.https_enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.restapi import RESTComponentImp
            return RESTComponentImp()
        return RESTComponentMock()


@testcomponent
class RESTComponentMock(RESTComponent):
    rest_manager = Mock()
