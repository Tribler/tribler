from __future__ import annotations

import logging
import mimetypes

from aiohttp import ClientSession, web

import tribler
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
        self.app.add_routes([web.get("/{path:.*}", self.return_files)])

        self.webui_root = tribler.get_webui_root()
        self.has_dist = (self.webui_root / "dist").exists()
        self.session = ClientSession() if not self.has_dist else None

    async def return_files(self, request: web.Request) -> RESTResponse | web.FileResponse:
        """
        Return the file at the requested path.
        """
        path = request.match_info["path"] or "index.html"

        if self.session:
            async with self.session.get(f"http://localhost:5173/{path}") as client_response:
                return RESTResponse(body=await client_response.read(), content_type=client_response.content_type)
        else:
            resource = self.webui_root / "dist" / path
            response = web.FileResponse(resource)
            if path.endswith(".tsx"):
                response.content_type = "application/javascript"
            elif path.endswith(".js"):
                # https://github.com/Tribler/tribler/issues/8279
                response.content_type = "application/javascript"
            elif path.endswith(".html"):
                response.content_type = "text/html"
            elif (guessed_type := mimetypes.guess_type(path)[0]) is not None:
                response.content_type = guessed_type
            else:
                response.content_type = "application/octet-stream"
            return response

    async def shutdown_task_manager(self) -> None:
        """
        Shutdown the taskmanager.
        """
        await super().shutdown_task_manager()
        if self.session:
            await self.session.close()
