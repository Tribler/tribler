from __future__ import absolute_import

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


class MatchmakersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your known matchmakers in the market community.
    """

    def render_GET(self, request):
        """
        .. http:get:: /market/matchmakers

        A GET request to this endpoint will return all known matchmakers.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/matchmakers

            **Example response**:

            .. sourcecode:: javascript

                {
                    "matchmakers": [{
                        "ip": "131.249.48.3",
                        "port": 7008
                    }]
                }
        """
        matchmakers = self.session.lm.market_community.matchmakers
        matchmakers_json = [{"ip": mm.address[0], "port": mm.address[1]} for mm in matchmakers]
        return json.twisted_dumps({"matchmakers": matchmakers_json})
