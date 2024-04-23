from __future__ import annotations

import logging
from asyncio import CancelledError, Future
from contextlib import suppress
from hashlib import sha1
from os.path import getsize
from typing import TYPE_CHECKING, Any, Dict, Iterable, TypedDict

import libtorrent as lt

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def check_handle(default=None):
    """
    Return the libtorrent handle if it's available, else return the default value.

    Author(s): Egbert Bouman
    """

    def wrap(f):
        def invoke_func(*args, **kwargs):
            download = args[0]
            if download.handle and download.handle.is_valid():
                return f(*args, **kwargs)
            return default

        return invoke_func

    return wrap


def require_handle(func):
    """
    Invoke the function once the handle is available. Returns a future that will fire once the function has completed.

    Author(s): Egbert Bouman
    """

    def invoke_func(*args, **kwargs):
        result_future = Future()

        def done_cb(fut):
            with suppress(CancelledError):
                handle = fut.result()

            if fut.cancelled() or result_future.done() or handle != download.handle or not handle.is_valid():
                logger.warning('Can not invoke function, handle is not valid or future is cancelled')
                result_future.set_result(None)
                return

            try:
                result = func(*args, **kwargs)
            except RuntimeError as e:
                # ignore runtime errors, for more info see: https://github.com/Tribler/tribler/pull/7783
                logger.exception(e)
                result_future.set_result(None)
            except Exception as e:
                logger.exception(e)
                result_future.set_exception(e)
            else:
                result_future.set_result(result)

        download = args[0]
        handle_future = download.get_handle()
        handle_future.add_done_callback(done_cb)
        return result_future

    return invoke_func


def check_vod(default=None):
    """
    Check if torrent is vod mode, else return default.
    """

    def wrap(f):
        def invoke_func(self, *args, **kwargs):
            if self.enabled:
                return f(self, *args, **kwargs)
            return default

        return invoke_func

    return wrap


def common_prefix(paths_list: list[Path]) -> Path:
    """
    Get the path prefixes component-wise.
    """
    base_set = set(paths_list[0].parents)
    for p in paths_list[1:]:
        base_set.intersection_update(set(p.parents))

    return sorted(base_set, reverse=True)[0]


def _existing_files(path_list: list[Path]) -> Iterable[Path]:
    for path in path_list:
        if not path.exists():
            msg = f"Path does not exist: {path}"
            raise OSError(msg)
        elif path.is_file():
            yield path


class TorrentFileResult(TypedDict):
    """
    A dictionary to describe a newly-created torrent.
    """

    success: bool
    base_dir: Path
    torrent_file_path: str | None
    metainfo: dict
    infohash: bytes


def create_torrent_file(file_path_list: list[Path], params: Dict[bytes, Any],  # noqa: C901
                        torrent_filepath: str | None = None) -> TorrentFileResult:
    """
    Create a torrent file from the given paths and parameters.

    If an output file path is omitted, no file will be written to disk.
    """
    fs = lt.file_storage()

    # filter all non-files
    path_list = list(_existing_files(file_path_list))

    # ACHTUNG!
    # In the case of a multi-file torrent, the torrent name plays the role of the toplevel dir name.
    # get the directory where these files are in. If there are multiple files, take the common directory they are in
    base_dir = (common_prefix(path_list).parent if len(path_list) > 1 else path_list[0].parent).absolute()
    for path in path_list:
        relative = path.relative_to(base_dir)
        fs.add_file(str(relative), getsize(str(path)))

    piece_size = params[b"piece length"] if params.get(b"piece length") else 0
    flags = lt.create_torrent_flags_t.optimize
    params = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in params.items()}

    torrent = lt.create_torrent(fs, piece_size=piece_size, flags=flags)
    if params.get(b"comment"):
        torrent.set_comment(params[b"comment"])
    if params.get(b"created by"):
        torrent.set_creator(params[b"created by"])
    # main tracker
    if params.get(b"announce"):
        torrent.add_tracker(params[b"announce"])
    # tracker list
    if params.get(b"announce-list"):
        tier = 1
        for tracker in params[b"announce-list"]:
            torrent.add_tracker(tracker[0], tier=tier)
            tier += 1
    # DHT nodes
    # http://www.bittorrent.org/beps/bep_0005.html
    if params.get(b"nodes"):
        for node in params[b"nodes"]:
            torrent.add_node(*node)
    # HTTP seeding
    # http://www.bittorrent.org/beps/bep_0017.html
    if params.get(b"httpseeds"):
        torrent.add_http_seed(params[b"httpseeds"])

    # Web seeding
    # http://www.bittorrent.org/beps/bep_0019.html
    if len(file_path_list) == 1 and params.get(b"urllist", False):
        torrent.add_url_seed(params[b"urllist"])

    # read the files and calculate the hashes
    lt.set_piece_hashes(torrent, str(base_dir))

    t1 = torrent.generate()
    torrent = lt.bencode(t1)

    if torrent_filepath:
        with open(torrent_filepath, "wb") as f:
            f.write(torrent)

    return {
        "success": True,
        "base_dir": base_dir,
        "torrent_file_path": torrent_filepath,
        "metainfo": torrent,
        "infohash": sha1(lt.bencode(t1[b"info"])).digest()
    }


def get_info_from_handle(handle: lt.torrent_handle) -> lt.torrent_info | None:
    """
    Call handle.torrent_file() and handle RuntimeErrors.
    """
    try:
        return handle.torrent_file()
    except AttributeError as ae:
        logger.warning("No torrent info found from handle: %s", str(ae))
        return None
    except RuntimeError as e:  # This can happen when the torrent handle is invalid.
        logger.warning("Got exception when fetching info from handle: %s", str(e))
        return None
