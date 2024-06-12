import contextlib
import logging
import sys
from pathlib import Path

import win32api
from aiohttp import web

from tribler.core.restapi.rest_endpoint import HTTP_NOT_FOUND, RESTEndpoint, RESTResponse


class FileEndpoint(RESTEndpoint):
    """
    This endpoint allows clients to view the server's file structure remotely.
    """

    path = '/api/files'

    def __init__(self) -> None:
        """
        Create a new file endpoint.
        """
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.app.add_routes([web.get('/browse', self.browse),
                             web.get('/list', self.list)])

    async def browse(self, request: web.Request) -> RESTResponse:
        """
        Return all files/directories found in the specified path.
        """
        path = request.query.get('path', "")
        show_files = request.query.get('files') == "1"

        # Deal with getting the drives on Windows
        if path == "/" and sys.platform == 'win32':
            paths = []
            for drive in win32api.GetLogicalDriveStrings().split("\000"):
                if not drive:
                    continue
                paths.append(
                    {
                        "name": drive,
                        "path": drive,
                        "dir": True,
                    }
                )
            return RESTResponse({"current": "Root",
                                 "paths": paths})

        # Move up until we find a directory
        path = Path(path).resolve()
        while not path.is_dir():
            path = path.parent

        # Get all files/subdirs
        results = []
        for file in path.iterdir():
            if not file.is_dir() and not show_files:
                continue
            with contextlib.suppress(PermissionError):
                results.append({"name": file.name, "path": str(file.resolve()), "dir": file.is_dir()})

        results.sort(key=lambda f: not f["dir"])

        # Get parent path (if available)
        results.insert(0, {
            "name": "..",
            "path": str(path.parent.resolve()) if path != path.parent else "/",
            "dir": True,
        })

        return RESTResponse({"current": str(path.resolve()),
                             "paths": results})

    async def list(self, request: web.Request) -> RESTResponse:
        """
        Return all files found in the specified path.
        """
        path = Path(request.query.get('path', ""))
        recursively = request.query.get('recursively') != "0"

        if not path.exists():
            return RESTResponse({"error": f"Directory {path} does not exist"}, status=HTTP_NOT_FOUND)

        results = [{"name": file.name,
                    "path": str(file.resolve())}
                   for file in path.glob(f"{'**/' if recursively else ''}*") if file.is_file()]

        return RESTResponse({"paths": results})
