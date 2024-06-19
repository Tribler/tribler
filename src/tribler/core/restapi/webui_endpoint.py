import logging
import mimetypes
import pathlib

from aiohttp import ClientSession, web

from tribler.core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class WebUIEndpoint(RESTEndpoint):
    """
    This endpoint serves files used by the web UI.
    """

    path = '/ui'

    def __init__(self) -> None:
        """
        Create a new webUI endpoint.
        """
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app.add_routes([web.get('/{path:.*}', self.return_files)])

        self.webui_root = (pathlib.Path(__file__).absolute() / "../../../ui/").resolve()
        self.has_dist = (self.webui_root / 'dist').exists()
        self.session = ClientSession() if not self.has_dist else None

    async def return_files(self, request: web.Request) -> RESTResponse:
        """
        Return the file at the requested path.
        """
        path = request.match_info['path'] or 'index.html'

        if self.session:
            async with self.session.get(f'http://localhost:5173/{path}') as response:
                return web.Response(body=await response.read(), content_type=response.content_type)
        else:
            resource = self.webui_root / 'dist' / path
            response = web.FileResponse(resource)
            response.content_type = 'application/javascript' if path.endswith('.tsx') else mimetypes.guess_type(path)[0]
            return response

    async def shutdown_task_manager(self) -> None:
        """
        Shutdown the taskmanager.
        """
        await super().shutdown_task_manager()
        if self.session:
            await self.session.close()
