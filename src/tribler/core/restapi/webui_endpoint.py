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

    path = "/ui"

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
            headers = {}
            if path.endswith(".tsx"):
                headers["Content-Type"] = "application/javascript"
            elif path.endswith(".js"):
                # https://github.com/Tribler/tribler/issues/8279
                headers["Content-Type"] = "application/javascript"
            elif path.endswith(".html"):
                headers["Content-Type"] = "text/html"
                headers["Cache-Control"] = "no-store"
            elif (guessed_type := mimetypes.guess_type(path)[0]) is not None:
                headers["Content-Type"] = guessed_type
            else:
                headers["Content-Type"] = "application/octet-stream"
            return web.FileResponse(resource, headers=headers)

    async def shutdown_task_manager(self) -> None:
        """
        Shutdown the taskmanager.
        """
        await super().shutdown_task_manager()
        if self.session:
            await self.session.close()
