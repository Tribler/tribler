import contextlib
import logging
import os
import platform
from pathlib import Path

from aiohttp import web

from tribler.core.restapi.rest_endpoint import HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND, RESTEndpoint, RESTResponse

if platform.system() == 'Windows':
    import win32api


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
                             web.get('/list', self.list),
                             web.get('/create', self.create)])

    async def browse(self, request: web.Request) -> RESTResponse:
        """
        Return all files/directories found in the specified path.
        """
        path = request.query.get('path', "")
        show_files = request.query.get('files') == "1"

        # Deal with getting the drives on Windows
        if path == "/" and platform.system() == 'Windows':
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
                                 "paths": paths,
                                 "separator": os.path.sep})

        # Move up until we find a directory
        parent_path = Path(path).resolve()
        while not parent_path.is_dir():
            parent_path = parent_path.parent

        # Get all files/subdirs
        results = []
        for file in parent_path.iterdir():
            if not file.is_dir() and not show_files:
                continue
            with contextlib.suppress(PermissionError):
                results.append({"name": file.name, "path": str(file.resolve()), "dir": file.is_dir()})

        results.sort(key=lambda f: not f["dir"])

        # Get parent path (if available)
        results.insert(0, {
            "name": "..",
            "path": str(parent_path.parent.resolve()) if parent_path != parent_path.parent else "/",
            "dir": True,
        })

        return RESTResponse({"current": str(parent_path.resolve()),
                             "paths": results,
                             "separator": os.path.sep})

    async def list(self, request: web.Request) -> RESTResponse:
        """
        Return all files found in the specified path.
        """
        path = Path(request.query.get('path', ""))
        recursively = request.query.get('recursively') != "0"

        if not path.exists():
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": f"Directory {path} does not exist"
                                }}, status=HTTP_NOT_FOUND)

        results = [{"name": file.name,
                    "path": str(file.resolve())}
                   for file in path.glob(f"{'**/' if recursively else ''}*") if file.is_file()]

        return RESTResponse({"paths": results})

    async def create(self, request: web.Request) -> RESTResponse:
        """
        Create the specified path.
        """
        path = Path(request.query.get("path", ""))
        recursively = request.query.get("recursively", "1") != "0"
        try:
            path.mkdir(parents=recursively, exist_ok=True)
        except (OSError, FileNotFoundError) as e:
            return RESTResponse({"error": {
                "handled": True,
                "message": str(e)
            }}, status=HTTP_INTERNAL_SERVER_ERROR)
        return RESTResponse({"paths": [{"name": path.name, "path": str(path.resolve()), "dir": True}]})
