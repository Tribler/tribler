from tribler_core.components.base import Component
from tribler_core.restapi.rest_manager import RESTManager


class RESTComponent(Component):
    rest_manager: RESTManager
