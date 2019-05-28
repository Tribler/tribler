from __future__ import absolute_import

import json
from random import randint

from twisted.web import resource


class StatisticsEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def __init__(self):
        resource.Resource.__init__(self)

        child_handler_dict = {"tribler": StatisticsTriblerEndpoint, "ipv8": StatisticsIPv8Endpoint}

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls())


class StatisticsTriblerEndpoint(resource.Resource):
    """
    This class handles requests regarding Tribler statistics.
    """
    def render_GET(self, _request):
        return json.dumps({'tribler_statistics': {
            "db_size": randint(1000, 1000000),
            "num_channels": randint(1, 100),
            "num_torrents": randint(1000, 10000)
        }})


class StatisticsIPv8Endpoint(resource.Resource):
    """
    This class handles requests regarding IPv8 statistics.
    """
    def render_GET(self, _request):
        return json.dumps({'ipv8_statistics': {
            "total_up": 13423,
            "total_down": 3252
        }})
