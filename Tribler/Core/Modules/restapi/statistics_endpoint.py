import json

from twisted.web import resource


class StatisticsEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"tribler": StatisticsTriblerEndpoint, "dispersy": StatisticsDispersyEndpoint,
                              "communities": StatisticsCommunitiesEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class StatisticsTriblerEndpoint(resource.Resource):
    """
    This class handles requests regarding Tribler statistics.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /statistics/tribler

        A GET request to this endpoint returns general statistics in Tribler.
        The size of the Tribler database is in bytes.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/tribler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "tribler_statistics": {
                        "num_channels": 1234,
                        "database_size": 384923,
                        "torrent_queue_stats": [{
                            "failed": 2,
                            "total": 9,
                            "type": "TFTP",
                            "pending": 1,
                            "success": 6
                        }, ...]
                    }
                }
        """
        return json.dumps({'tribler_statistics': self.session.get_tribler_statistics()})


class StatisticsDispersyEndpoint(resource.Resource):
    """
    This class handles requests regarding Dispersy statistics.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /statistics/dispersy

        A GET request to this endpoint returns general statistics in Dispersy.
        The returned runtime is the amount of seconds that Dispersy is active. The total uploaded and total downloaded
        statistics are in bytes.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/dispersy

            **Example response**:

            .. sourcecode:: javascript

                {
                    "dispersy_statistics": {
                        "wan_address": "123.321.456.654:1234",
                        "lan_address": "192.168.1.2:1435",
                        "connection": "unknown",
                        "runtime": 859.34,
                        "total_downloaded": 538.53,
                        "total_uploaded": 983.24,
                        "packets_sent": 43,
                        "packets_received": 89,
                        ...
                    }
                }
        """
        return json.dumps({'dispersy_statistics': self.session.get_dispersy_statistics()})


class StatisticsCommunitiesEndpoint(resource.Resource):
    """
    This class handles requests regarding Dispersy communities statistics.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /statistics/communities

        A GET request to this endpoint returns general statistics of active Dispersy communities.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/communities

            **Example response**:

            .. sourcecode:: javascript

                {
                    "community_statistics": [{
                        "identifier": "48d04e922dec4430daf22400c9d4cc5a3a53b27d",
                        "member": "a66ebac9d88a239ef348a030d5ed3837868fc06d",
                        "candidates": 43,
                        "global_time": 42,
                        "classification", "ChannelCommunity",
                        "packets_sent": 43,
                        "packets_received": 89,
                        ...
                    }, { ... }]
                }
        """
        return json.dumps({'community_statistics': self.session.get_community_statistics()})
