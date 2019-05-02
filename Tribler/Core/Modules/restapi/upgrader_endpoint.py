from __future__ import absolute_import

import logging

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class UpgraderEndpoint(resource.Resource):
    """
    With this endpoint you can control DB upgrade process of Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def render_DELETE(self, _):
        """
        .. http:put:: /upgrader

        A PUT request to this endpoint will skip the DB upgrade process, if it is running.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/upgrader

            **Example response**:

            .. sourcecode:: javascript

                {
                    "skip": True
                }
        """

        if self.session.upgrader:
            self.session.upgrader.skip()

        return json.twisted_dumps({"skip": True})
