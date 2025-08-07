from __future__ import annotations

import logging
from asyncio.exceptions import TimeoutError as AsyncTimeoutError
from binascii import hexlify
from pathlib import Path
from ssl import SSLError
from typing import TYPE_CHECKING, Literal, TypedDict, cast, overload

import libtorrent as lt
from aiohttp import (
    BaseConnector,
    ClientConnectorCertificateError,
    ClientConnectorError,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    ServerConnectionError,
    web,
)
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from marshmallow.fields import Boolean, String
from yarl import URL

from tribler.core.database.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.libtorrent.uris import unshorten, url_to_path
from tribler.core.notifier import Notification
from tribler.core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    RESTEndpoint,
    RESTResponse,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aiohttp.typedefs import LooseHeaders
    from aiohttp.web_request import Request

    from tribler.core.libtorrent.download_manager.download_manager import DownloadManager

logger = logging.getLogger(__name__)


class JSONMiniFileInfo(TypedDict):
    """
    A minimal JSON dict to describe file info.
    """

    index: int
    name: str
    size: int


def recursive_unicode(obj: Iterable, ignore_errors: bool = False) -> Iterable:
    """
    Converts any bytes within a data structure to unicode strings. Bytes are assumed to be UTF-8 encoded text.

    :param obj: object comprised of lists/dicts/strings/bytes
    :param ignore_errors: if bytes are not valid unicode, don't attempt to decode them.
    :return: obj: object comprised of lists/dicts/strings
    """
    if isinstance(obj, dict):
        return {recursive_unicode(k, ignore_errors): recursive_unicode(v, ignore_errors) for k, v in obj.items()}
    if isinstance(obj, list):
        return [recursive_unicode(i, ignore_errors) for i in obj]
    if isinstance(obj, bytes):
        try:
            return obj.decode()
        except UnicodeDecodeError:
            if ignore_errors:
                return "".join(chr(c) for c in obj)
            raise
    return obj


@overload
async def query_uri(uri: str, connector: BaseConnector | None = None, headers: LooseHeaders | None = None,
                    timeout: ClientTimeout | None = None, return_json: Literal[False] = False,
                    valid_cert: bool = True) -> bytes: ...

@overload
async def query_uri(uri: str, connector: BaseConnector | None = None, headers: LooseHeaders | None = None,
                    timeout: ClientTimeout | None = None, return_json: Literal[True] = True,
                    valid_cert: bool = True) -> dict: ...

async def query_uri(uri: str, connector: BaseConnector | None = None, headers: LooseHeaders | None = None,
                    timeout: ClientTimeout | None = None, return_json: bool = False,
                    valid_cert: bool = True) -> bytes | dict:
    """
    Retrieve the response for the given aiohttp context.
    """
    kwargs: dict = {"headers": headers}
    if timeout:
        # ClientSession uses a sentinel object for the default timeout. Therefore, it should only be specified if an
        # actual value has been passed to this function.
        kwargs["timeout"] = timeout

    async with ClientSession(connector=connector, raise_for_status=True) as session, \
            await session.get(uri, ssl=valid_cert, **kwargs) as response:
        if return_json:
            return await response.json(content_type=None)
        return await response.read()


class TorrentInfoEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    path = "/api/torrentinfo"

    def __init__(self, download_manager: DownloadManager) -> None:
        """
        Create a new torrent info endpoint.
        """
        super().__init__()
        self.download_manager = download_manager
        self.app.add_routes([web.get("", self.get_torrent_info),
                             web.put("", self.get_torrent_info_from_file)])

    def get_files(self, tdef: TorrentDef) -> list[JSONMiniFileInfo]:
        """
        Get a list of files from the given torrent definition.
        """
        remapped_indices = tdef.get_file_indices()
        torrent_info = cast("lt.torrent_info", tdef.atp.ti)
        return [
            JSONMiniFileInfo(
                index=fi,
                name=(str(Path(torrent_info.file_at(fi).path).relative_to(torrent_info.name()))
                      if len(remapped_indices) > 1 else str(Path(torrent_info.file_at(fi).path))),
                size=torrent_info.file_at(fi).size,
            )
            for fi in remapped_indices
        ]

    @docs(
        tags=["Libtorrent"],
        summary="Return metainfo from a torrent found at a provided URI.",
        parameters=[
            {
                "in": "query",
                "name": "uri",
                "description": "URI for which to return torrent information. This URI can either represent "
                "a file location, a magnet link or a HTTP(S) url.",
                "type": "string",
                "required": True,
            },
            {
                "in": "query",
                "name": "hops",
                "description": "The number of anonymization hops to use.",
                "type": "number",
                "required": False,
            },
            {
                "in": "query",
                "name": "skipmagnet",
                "description": "Don't resolve magnet link metainfo, if you want an immediate response.",
                "type": "boolean",
                "required": False,
            },
        ],
        responses={
            200: {
                "description": "Return a hex-encoded json-encoded string with torrent metainfo",
                "schema": schema(
                    GetMetainfoResponse={"metainfo": String, "download_exists": Boolean, "valid_certificate": Boolean}
                ),
            }
        },
    )
    async def get_torrent_info(self, request: Request) -> RESTResponse:  # noqa: C901, PLR0911, PLR0912, PLR0915
        """
        Return metainfo from a torrent found at a provided URI.
        """
        params = request.query
        hops = params.get("hops")
        i_hops = 0
        p_uri = params.get("uri")
        skip_check_metainfo = params.get("skipmagnet", "false") in ["true", "1"]
        self._logger.info("URI: %s", p_uri)
        if hops:
            try:
                i_hops = int(hops)
            except ValueError:
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": f"wrong value of 'hops' parameter: {hops}"
                                    }}, status=HTTP_BAD_REQUEST)

        if not p_uri:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "uri parameter missing"
                                }}, status=HTTP_BAD_REQUEST)

        uri, valid_cert = await unshorten(p_uri)
        scheme = URL(uri).scheme

        torrent_def: TorrentDef | None = None
        if scheme == "file":
            file_path = url_to_path(uri)
            try:
                torrent_def = await TorrentDef.load(file_path)
                skip_check_metainfo = False
            except (OSError, TypeError, ValueError, RuntimeError):
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": f"error while decoding torrent file: {file_path}"
                                    }}, status=HTTP_INTERNAL_SERVER_ERROR)
        elif scheme in ("http", "https"):
            try:
                try:
                    response = await query_uri(uri)
                except ClientConnectorCertificateError:
                    response = await query_uri(uri, valid_cert=False)
                    valid_cert = False
            except (ServerConnectionError, ClientResponseError, SSLError, ClientConnectorError,
                    AsyncTimeoutError, ValueError) as e:
                self._logger.warning("Error while querying http uri: %s", str(e))
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": str(e)
                                    }}, status=HTTP_INTERNAL_SERVER_ERROR)

            if not isinstance(response, bytes):
                self._logger.warning("Error while reading response from http uri: %s", repr(response))
                return RESTResponse({"error": {
                                        "handled": True,
                                        "message": "Error while reading response from http uri"
                                    }}, status=HTTP_INTERNAL_SERVER_ERROR)

            if response.startswith(b'magnet'):
                try:
                    infohash = lt.parse_magnet_uri(uri).info_hashes.v1.to_bytes()
                except RuntimeError as e:
                    return RESTResponse(
                        {"error": {
                            "handled": True,
                            "message": f'Error while getting an infohash from magnet: {e.__class__.__name__}: {e}'
                        }}, status=HTTP_INTERNAL_SERVER_ERROR
                    )

                if not skip_check_metainfo:
                    lookup = (await self.download_manager.get_metainfo(infohash, timeout=60, hops=i_hops,
                                                                       url=response.decode()))
                    if lookup is not None:
                        torrent_def = lookup["tdef"]
            else:
                try:
                    torrent_def = TorrentDef.load_from_memory(response)
                    skip_check_metainfo = False
                except ValueError:
                    return RESTResponse(
                        {"error": {
                            "handled": True,
                            "message": f"Could not read torrent from {uri}"
                        }}, status=HTTP_INTERNAL_SERVER_ERROR
                    )
        elif scheme == "magnet":
            self._logger.info("magnet scheme detected")

            try:
                infohash = lt.parse_magnet_uri(uri).info_hashes.v1.to_bytes()
            except RuntimeError as e:
                return RESTResponse(
                    {"error": {
                        "handled": True,
                        "message": f'Error while getting an infohash from magnet: {e.__class__.__name__}: {e}'
                    }}, status=HTTP_BAD_REQUEST
                )
            if not skip_check_metainfo:
                lookup = await self.download_manager.get_metainfo(infohash, timeout=60, hops=i_hops, url=uri)
                if lookup is not None:
                    torrent_def = lookup["tdef"]
        else:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "invalid uri"
                                }}, status=HTTP_BAD_REQUEST)

        if skip_check_metainfo:
            return RESTResponse({"metainfo": "", "download_exists": False, "valid_certificate": True})

        if not torrent_def or not torrent_def.atp.ti:
            return RESTResponse({"error": {
                                    "handled": True,
                                    "message": "metainfo error"
                                }}, status=HTTP_INTERNAL_SERVER_ERROR)

        # Add the torrent to metadata.db
        metadata_dict = tdef_to_metadata_dict(torrent_def)
        self.download_manager.notifier.notify(Notification.torrent_metadata_added, metadata=metadata_dict)

        download = self.download_manager.downloads.get(metadata_dict["infohash"])
        metainfo_lookup = self.download_manager.metainfo_requests.get(metadata_dict["infohash"])
        metainfo_download = metainfo_lookup.download if metainfo_lookup else None
        download_is_metainfo_request = download == metainfo_download

        return RESTResponse({"files": self.get_files(torrent_def),
                             "name": cast("lt.torrent_info", torrent_def.atp.ti).name(),
                             "download_exists": download and not download_is_metainfo_request,
                             "valid_certificate": valid_cert})

    @docs(
        tags=["Libtorrent"],
        summary="Return metainfo from a torrent found at a provided .torrent file.",
        responses={
            200: {
                "description": "Return a hex-encoded json-encoded string with torrent metainfo",
                "schema": schema(GetMetainfoResponse={"metainfo": String})
            }
        }
    )
    async def get_torrent_info_from_file(self, request: web.Request) -> RESTResponse:
        """
        Return metainfo from a torrent found at a provided .torrent file.
        """
        tdef = TorrentDef.load_from_memory(await request.read())
        infohash = tdef.infohash

        # Check if the torrent is already in the downloads
        download = self.download_manager.downloads.get(infohash)
        metainfo_lookup = self.download_manager.metainfo_requests.get(infohash)
        metainfo_download = metainfo_lookup.download if metainfo_lookup else None
        requesting_metainfo = download == metainfo_download

        return RESTResponse({"infohash": hexlify(infohash).decode(),
                             "files": self.get_files(tdef),
                             "name": tdef.name,
                             "download_exists": download and not requesting_metainfo})
