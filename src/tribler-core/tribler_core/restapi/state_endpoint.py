from aiohttp import web

from tribler_common.simpledefs import NTFY, STATE_EXCEPTION, STATE_STARTED, STATE_STARTING, STATE_UPGRADING

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StateEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding the state of Tribler.
    """

    def __init__(self, session):
        super(StateEndpoint, self).__init__(session)
        self.tribler_state = STATE_STARTING
        self.last_exception = None

        self.session.notifier.add_observer(NTFY.UPGRADER_STARTED, self.on_tribler_upgrade_started)
        self.session.notifier.add_observer(NTFY.UPGRADER_DONE, self.on_tribler_upgrade_finished)
        self.session.notifier.add_observer(NTFY.TRIBLER_STARTED, self.on_tribler_started)

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_state)])

    def on_tribler_upgrade_started(self, *_):
        self.tribler_state = STATE_UPGRADING

    def on_tribler_upgrade_finished(self, *_):
        self.tribler_state = STATE_STARTING

    def on_tribler_started(self, *_):
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
