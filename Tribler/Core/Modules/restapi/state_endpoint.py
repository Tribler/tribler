from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from Tribler.Core.simpledefs import (NTFY_FINISHED, NTFY_STARTED, NTFY_TRIBLER, NTFY_UPGRADER, STATE_EXCEPTION,
                                     STATE_STARTED, STATE_STARTING, STATE_UPGRADING)


class StateEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding the state of Tribler.
    """

    def __init__(self, session):
        super(StateEndpoint, self).__init__(session)
        self.tribler_state = STATE_STARTING
        self.last_exception = None

        self.session.add_observer(self.on_tribler_upgrade_started, NTFY_UPGRADER, [NTFY_STARTED])
        self.session.add_observer(self.on_tribler_upgrade_finished, NTFY_UPGRADER, [NTFY_FINISHED])
        self.session.add_observer(self.on_tribler_started, NTFY_TRIBLER, [NTFY_STARTED])

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_state)])

    def on_tribler_upgrade_started(self, subject, changetype, objectID, *args):
        self.tribler_state = STATE_UPGRADING

    def on_tribler_upgrade_finished(self, subject, changetype, objectID, *args):
        self.tribler_state = STATE_STARTING

    def on_tribler_started(self, subject, changetype, objectID, *args):
        self.tribler_state = STATE_STARTED

    def on_tribler_exception(self, exception_text):
        self.tribler_state = STATE_EXCEPTION
        self.last_exception = exception_text

    async def get_state(self, request):
        """
        .. http:get:: /state

        A GET request to this endpoint returns the current state of the Tribler core. There are three states:
        - STARTING: The core of Tribler is starting
        - UPGRADING: The upgrader is active
        - STARTED: The Tribler core has started
        - EXCEPTION: An exception has occurred in the core

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/state

            **Example response**:

            .. sourcecode:: javascript

                {
                    "state": "STARTED",
                    "last_exception": None,
                    "readable_state": ""
                }
        """
        return RESTResponse({
            "state": self.tribler_state,
            "last_exception": self.last_exception,
            "readable_state": self.session.readable_status
        })
