from aiohttp import web

from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTEndpoint, RESTResponse

SKIP_DB_UPGRADE_STR = "skip_db_upgrade"


class UpgraderEndpoint(RESTEndpoint):
    """
    With this endpoint you can control DB upgrade process of Tribler.
    """

    def setup_routes(self):
        self.app.add_routes([web.post('', self.skip_upgrade)])

    async def skip_upgrade(self, request):
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
        parameters = await request.json()
        if SKIP_DB_UPGRADE_STR not in parameters:
            return RESTResponse({"error": "attribute to change is missing"}, status=HTTP_BAD_REQUEST)
        elif not self.session.upgrader:
            return RESTResponse({"error": "upgrader is not running"}, status=HTTP_NOT_FOUND)

        if self.session.upgrader and parameters[SKIP_DB_UPGRADE_STR]:
            self.session.upgrader.skip()

        return RESTResponse({SKIP_DB_UPGRADE_STR: True})
