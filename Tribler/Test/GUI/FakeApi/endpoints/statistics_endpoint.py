import json
from random import randint

from twisted.web import resource


class StatisticsEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def __init__(self):
        resource.Resource.__init__(self)

        child_handler_dict = {"tribler": StatisticsTriblerEndpoint, "dispersy": StatisticsDispersyEndpoint,
                              "communities": StatisticsCommunitiesEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls())


class StatisticsTriblerEndpoint(resource.Resource):
    """
    This class handles requests regarding Tribler statistics.
    """
    def render_GET(self, request):
        return json.dumps({'tribler_statistics': {
            "num_channels": randint(5, 100),
            "database_size": randint(1000, 1000000),
            "torrents": {
                "num_collected": randint(5, 100),
                "total_size": randint(1000, 100000),
                "num_files": randint(5, 100)
            }
        }})


class StatisticsDispersyEndpoint(resource.Resource):
    """
    This class handles requests regarding Dispersy statistics.
    """
    def render_GET(self, request):
        return json.dumps({'dispersy_statistics': self.session.get_dispersy_statistics()})


class StatisticsCommunitiesEndpoint(resource.Resource):
    """
    This class handles requests regarding Dispersy communities statistics.
    """
    def render_GET(self, request):
        return json.dumps({'community_statistics': self.session.get_community_statistics()})
