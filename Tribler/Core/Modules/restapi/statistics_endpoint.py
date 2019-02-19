from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class StatisticsEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {
            "tribler": StatisticsTriblerEndpoint,
            "dispersy": StatisticsDispersyEndpoint,
            "ipv8": StatisticsIPv8Endpoint,
        }

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


class StatisticsIPv8Endpoint(resource.Resource):
    """
    This class handles requests regarding IPv8 statistics.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /statistics/ipv8

        A GET request to this endpoint returns general statistics of IPv8.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/ipv8

            **Example response**:

            .. sourcecode:: javascript

                {
                    "ipv8_statistics": {
                        "total_up": 3424324,
                        "total_down": 859484
                    }
                }
        """
        return json.dumps({
            'ipv8_statistics': self.session.get_ipv8_statistics()
        })
