from __future__ import absolute_import

import logging

from six import viewitems

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json

SKIP_DB_UPGRADE_STR = "skip_db_upgrade"


class UpgraderEndpoint(resource.Resource):
    """
    With this endpoint you can control DB upgrade process of Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def render_POST(self, request):
        """
        .. http:post:: /upgrader

        A POST request to this endpoint will skip the DB upgrade process, if it is running.

            **Example request**:

            .. sourcecode:: javascript

                {
                    "skip_db_upgrade": true
                }


                curl -X POST http://localhost:8085/upgrader

            **Example response**:

            .. sourcecode:: javascript

                {
                    "skip_db_upgrade": true
                }
        """

        parameters_raw = http.parse_qs(request.content.read(), 1)
        parameters = {}

        # FIXME: make all endpoints Unicode-compatible in a unified way
        for param, val in viewitems(parameters_raw):
            parameters.update({param: [item.decode('utf-8') for item in val]})

        if SKIP_DB_UPGRADE_STR not in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "attribute to change is missing"})
        elif not self.session.upgrader:
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "upgrader is not running"})

        if self.session.upgrader and parameters[SKIP_DB_UPGRADE_STR]:
            self.session.upgrader.skip()

        return json.twisted_dumps({SKIP_DB_UPGRADE_STR: True})
