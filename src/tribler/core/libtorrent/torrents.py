from __future__ import annotations

import logging
from asyncio import CancelledError, Future
from contextlib import suppress
from functools import wraps
from hashlib import sha1
from os.path import getsize
from typing import TYPE_CHECKING, Concatenate, TypedDict, cast

import libtorrent as lt

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from tribler.core.libtorrent.download_manager.download import Download
    from tribler.core.libtorrent.torrentdef import TorrentParameters

logger = logging.getLogger(__name__)


def check_handle[**WrappedParams, WrappedReturn](
        default: WrappedReturn
    ) -> Callable[[Callable[Concatenate[Download, lt.torrent_handle, WrappedParams], WrappedReturn]],
                  Callable[Concatenate[Download, WrappedParams], WrappedReturn]]:
    """
    Return the libtorrent handle if it's available, else return the default value.

    Author(s): Egbert Bouman
    """

    def wrap(
            f: Callable[Concatenate[Download, lt.torrent_handle, WrappedParams], WrappedReturn]
    ) -> Callable[Concatenate[Download, WrappedParams], WrappedReturn]:
        @wraps(f)
        def invoke_func(self: Download,
                        *args: WrappedParams.args, **kwargs: WrappedParams.kwargs
                        ) -> WrappedReturn:
            if self.handle and self.handle.is_valid():
                return f(self, self.handle, *args, **kwargs)
            return default

        return invoke_func

    return wrap


def require_handle[**WrappedParams, WrappedReturn](
        func: Callable[Concatenate[Download, lt.torrent_handle, WrappedParams], WrappedReturn]
    ) -> Callable[Concatenate[Download, WrappedParams], Future[WrappedReturn | None]]:
    """
    Invoke the function once the handle is available. Returns a future that will fire once the function has completed.

    Author(s): Egbert Bouman
    """

    def invoke_func(self: Download,
                    *args: WrappedParams.args, **kwargs: WrappedParams.kwargs
                    ) -> Future[WrappedReturn | None]:
        result_future: Future[WrappedReturn | None] = Future()

        def done_cb(fut: Future[lt.torrent_handle]) -> None:
            with suppress(CancelledError):
                handle = fut.result()

            if fut.cancelled() or result_future.done() or handle != self.handle or not handle.is_valid():
                logger.warning("Can not invoke function, handle is not valid or future is cancelled")
                result_future.set_result(None)
                return

            try:
                result = func(self, cast("lt.torrent_handle", fut.result()), *args, **kwargs)
            except RuntimeError as e:
                # ignore runtime errors, for more info see: https://github.com/Tribler/tribler/pull/7783
                logger.exception(e)
                result_future.set_result(None)
            except Exception as e:
                logger.exception(e)
                result_future.set_exception(e)
            else:
                result_future.set_result(result)

        handle_future = self.get_handle()
        handle_future.add_done_callback(done_cb)
        return result_future

    return invoke_func


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
    metainfo: bytes
    infohash: bytes


def create_torrent_file(file_path_list: list[Path], params: TorrentParameters,  # noqa: C901
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

    piece_size = params.get(b"piece length", 0)
    flag_v1_only = 2**6  # Backward compatibility for libtorrent < 2.x
    flags = lt.create_torrent_flags_t.optimize | flag_v1_only

    torrent = lt.create_torrent(fs, piece_size=piece_size, flags=flags)
    if (user_comment := params.get(b"comment")) is not None:
        torrent.set_comment(user_comment.decode())
    if (user_created_by := params.get(b"created by")) is not None:
        torrent.set_creator(user_created_by.decode())
    # main tracker
    if (user_announce := params.get(b"announce")) is not None:
        torrent.add_tracker(user_announce.decode())
    # tracker list
    if (user_announce_list := params.get(b"announce-list")) is not None:
        tier = 1
        for tracker in user_announce_list:
            torrent.add_tracker(tracker[0].decode(), tier=tier)
            tier += 1
    # DHT nodes
    # http://www.bittorrent.org/beps/bep_0005.html
    if (user_nodes := params.get(b"nodes")) is not None:
        for node in user_nodes:
            torrent.add_node(node[0].decode(), node[1])
    # HTTP seeding
    # http://www.bittorrent.org/beps/bep_0017.html
    if (user_http_seeds := params.get(b"httpseeds")) is not None:
        torrent.add_http_seed(user_http_seeds.decode())

    # Web seeding
    # http://www.bittorrent.org/beps/bep_0019.html
    if len(file_path_list) == 1 and (user_urllist := params.get(b"urllist")) is not None:
        torrent.add_url_seed(user_urllist.decode())

    # read the files and calculate the hashes
    lt.set_piece_hashes(torrent, str(base_dir))

    t1 = torrent.generate()
    torrent_bytes = lt.bencode(t1)

    if torrent_filepath:
        with open(torrent_filepath, "wb") as f:
            f.write(torrent_bytes)

    return {
        "success": True,
        "base_dir": base_dir,
        "torrent_file_path": torrent_filepath,
        "metainfo": torrent_bytes,
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
