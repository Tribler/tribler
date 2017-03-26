import json

from twisted.web import resource


class AliveEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding heartbeats in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /variables

        A GET request to this endpoint returns a basic response. This endpoint should be used by external applications
        to check whether the Tribler core is still alive.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/alive

            **Example response**:

            .. sourcecode:: javascript

                {
                    "alive": True
                }
        """
        return json.dumps({"alive": True})
