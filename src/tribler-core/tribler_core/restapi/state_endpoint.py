from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import String

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

    @docs(
        tags=["General"],
        summary="Return the current state of the Tribler core.",
        responses={
            200: {
                "schema": schema(TriblerStateResponse={
                    'state': (String, 'One of three stats: STARTING, UPGRADING, STARTED, EXCEPTION'),
                    'last_exception': String,
                    'readable_state': String
                })
            }
        }
    )
    async def get_state(self, request):
        return RESTResponse({
            "state": self.tribler_state,
            "last_exception": self.last_exception,
            "readable_state": self.session.readable_status
        })
