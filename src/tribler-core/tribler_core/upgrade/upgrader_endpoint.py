from aiohttp import web

from aiohttp_apispec import docs, json_schema

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean

from tribler_core.components.restapi.rest.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTEndpoint, \
    RESTResponse
from tribler_core.components.restapi.rest.schema import HandledErrorSchema
from tribler_core.utilities.utilities import froze_it

SKIP_DB_UPGRADE_STR = "skip_db_upgrade"


@froze_it
class UpgraderEndpoint(RESTEndpoint):
    """
    With this endpoint you can control DB upgrade process of Tribler.
    """

    def __init__(self, *args, **kwargs):
        RESTEndpoint.__init__(self, *args, **kwargs)
        self.upgrader = None

    def setup_routes(self):
        self.app.add_routes([web.post('', self.skip_upgrade)])

    @docs(
        tags=["Upgrader"],
        summary="Skip the DB upgrade process, if it is running.",
        responses={
            200: {
                "schema": schema(UpgraderResponse={'skip_db_upgrade': Boolean}),
                'examples': {"skip_db_upgrade": True}
            },
            HTTP_NOT_FOUND: {
                'schema': HandledErrorSchema
            },
            HTTP_BAD_REQUEST: {
                'schema': HandledErrorSchema
            }
        }
    )
    @json_schema(schema(UpgraderRequest={
        'skip_db_upgrade': (Boolean, 'Whether to skip the DB upgrade process or not'),
    }))
    async def skip_upgrade(self, request):
        parameters = await request.json()
        if SKIP_DB_UPGRADE_STR not in parameters:
            return RESTResponse({"error": "attribute to change is missing"}, status=HTTP_BAD_REQUEST)
        elif not self.upgrader:
            return RESTResponse({"error": "upgrader is not running"}, status=HTTP_NOT_FOUND)

        if self.upgrader and parameters[SKIP_DB_UPGRADE_STR]:
            self.upgrader.skip()

        return RESTResponse({SKIP_DB_UPGRADE_STR: True})
