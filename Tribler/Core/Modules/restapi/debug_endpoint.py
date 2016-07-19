import json

from twisted.web import http, resource

from Tribler.community.tunnel.tunnel_community import TunnelCommunity


class DebugEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding debug information in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"circuits": DebugCircuitsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class DebugCircuitsEndpoint(resource.Resource):
    """
    This class handles requests regarding the tunnel community debug information.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def get_tunnel_community(self):
        """
        Search for the tunnel community in the dispersy communities.
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, TunnelCommunity):
                return community
        return None

    def render_GET(self, request):
        """
        .. http:get:: /debug/circuits

        A GET request to this endpoint returns information about the built circuits in the tunnel community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/circuits

            **Example response**:

            .. sourcecode:: javascript

                {
                    "circuits": [
                        "id": 1234,
                        "state": "EXTENDING",
                        "goal_hops": 4,
                        "bytes_up": 45,
                        "bytes_down": 49,
                        "created": 1468176257,
                        "hops": [{
                            "host": "unknown"
                        }, {
                            "host": "39.95.147.20:8965"
                        }],
                        ...
                    ]
                }
        """
        tunnel_community = self.get_tunnel_community()
        if not tunnel_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "tunnel community not found"})

        circuits_json = []
        for circuit_id, circuit in tunnel_community.circuits.iteritems():
            item = {'id': circuit_id, 'state': str(circuit.state), 'goal_hops': circuit.goal_hops,
                    'bytes_up': circuit.bytes_up, 'bytes_down': circuit.bytes_down, 'created': circuit.creation_time}
            hops_array = []
            for hop in circuit.hops:
                hops_array.append({'host': 'unknown' if 'UNKNOWN HOST' in hop.host else '%s:%s' % (hop.host, hop.port)})

            item['hops'] = hops_array
            circuits_json.append(item)

        return json.dumps({'circuits': circuits_json})
