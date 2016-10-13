import json
from random import randint, choice

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
        return json.dumps({'dispersy_statistics': {
            "wan_address": "%d.%d.%d.%d:%d" %
                           (randint(1, 255), randint(1, 255), randint(1, 255), randint(1, 255), randint(1000, 65536)),
            "lan_address": "%d.%d.%d.%d:%d" %
                           (randint(1, 255), randint(1, 255), randint(1, 255), randint(1, 255), randint(1000, 65536)),
            "connection": "unknown",
            "runtime": randint(5, 2000),
            "total_downloaded": randint(10, 1000000),
            "total_uploaded": randint(10, 1000000),
            "packets_sent": randint(1, 1000),
            "packets_received": randint(1, 1000),
            "packets_success": randint(1, 1000),
            "packets_dropped": randint(1, 1000),
            "packets_delayed_sent": randint(1, 1000),
            "packets_delayed_success": randint(1, 1000),
            "packets_delayed_timeout": randint(1, 1000),
            "total_walk_attempts": randint(1, 1000),
            "total_walk_success": randint(1, 1000),
            "sync_messages_created": randint(1, 1000),
            "bloom_new": randint(1, 1000),
            "bloom_reused": randint(1, 1000),
            "bloom_skipped": randint(1, 1000)
        }})


class StatisticsCommunitiesEndpoint(resource.Resource):
    """
    This class handles requests regarding Dispersy communities statistics.
    """
    def render_GET(self, request):
        return json.dumps({'community_statistics': [{
            "identifier": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "member": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "classification": "Random1Community",
            "candidates": randint(0, 20)
        }, {
            "identifier": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "member": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "classification": "Random1Community",
            "candidates": randint(0, 20)
        }]})
