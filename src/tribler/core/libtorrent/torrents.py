from __future__ import annotations

import logging
import os
import shutil
from asyncio import CancelledError, Future
from contextlib import suppress
from functools import wraps
from hashlib import sha1
from os.path import getsize
from pathlib import Path
from typing import TYPE_CHECKING, Concatenate, TypedDict, cast

import libtorrent as lt

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from tribler.core.libtorrent.download_manager.download import Download

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


def _existing_files(path_list: list[Path], names: list[str] | None) -> Iterable[tuple[str, Path]]:
    if names is not None and len(path_list) != len(names):
        msg = "Source paths and their names in the torrent should be equal length lists!"
        raise ValueError(msg)
    for i, path in enumerate(path_list):
        if not path.exists():
            msg = f"Path does not exist: {path}"
            raise OSError(msg)
        elif path.is_file():
            if names is not None and names[i]:
                yield names[i], path.absolute()
            else:
                yield path.parts[-1], path.absolute()
        elif path.is_dir():
            for dirpath, _, files in path.walk(follow_symlinks=True):
                for file in files:
                    rel_file_path = (dirpath / file).relative_to(path)
                    if names is not None and names[i]:
                        yield str(Path(names[i]) / rel_file_path) , (dirpath / file).absolute()
                    else:
                        yield str(rel_file_path), (dirpath / file).absolute()


class TorrentFileResult(TypedDict):
    """
    A dictionary to describe a newly-created torrent.
    """

    success: bool
    base_dir: Path
    atp: lt.add_torrent_params
    infohash: bytes


def most_efficient_file_dupe(src: Path, dst: Path) -> None:
    """
    Get dst into src in the most efficient way possible:
     1. Symlink.
     2. Hardlink.
     3. Copy.

    If all three fail, we crash.
    """
    os.makedirs(str(dst.parent), exist_ok=True)
    try:
        dst.symlink_to(src, False)
    except OSError:
        try:
            dst.hardlink_to(src)
        except OSError:
            shutil.copy(str(src), str(dst))


def create_torrent_file(export_dir: str,  # noqa: C901,PLR0912,PLR0913
                        file_path_list: list[Path],
                        files_names: list[str] | None = None,
                        name: str | None = None,
                        announce: str | None = None,
                        announce_list: list[str] | None = None,
                        comment: str | None = None,
                        created_by: str | None = None,
                        http_seeds: list[str] | None = None,
                        nodes: list[tuple[str, int]] | None = None,
                        piece_size: int = 0,
                        url_list: list[str] | None = None) -> TorrentFileResult:
    """
    Create a torrent file from the given paths and parameters.

    If an output file path is omitted, no file will be written to disk.
    """
    fs = lt.file_storage()
    torrent_name = name or (common_prefix(file_path_list).parts or ["unknown"])[-1]

    path_list = list(_existing_files(file_path_list, files_names))
    base_dir = (Path(export_dir) / torrent_name) if len(path_list) > 1 else Path(export_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    for fname, src in path_list:
        in_torrent_file = base_dir / fname
        ignore = False
        if in_torrent_file.exists():
            logger.warning("Ignoring file %s, would overwrite existing file!", str(in_torrent_file))
        else:
            try:
                most_efficient_file_dupe(src, in_torrent_file)
            except OSError:
                ignore = True
                logger.exception("Failed to copy file %s, unable to copy!")
        if not ignore:
            fs.add_file(str(in_torrent_file.relative_to(export_dir)), getsize(str(src)))

    flag_v1_only = 2**6  # Backward compatibility for libtorrent < 2.x
    flags = lt.create_torrent_flags_t.optimize | flag_v1_only

    torrent = lt.create_torrent(fs, piece_size=piece_size, flags=flags)
    if comment is not None:
        torrent.set_comment(comment)
    if created_by is not None:
        torrent.set_creator(created_by)
    # main tracker
    if announce is not None:
        torrent.add_tracker(announce)
    # tracker list
    if announce_list is not None:
        tier = 1
        for tracker in announce_list:
            torrent.add_tracker(tracker, tier=tier)
            tier += 1
    # DHT nodes
    # http://www.bittorrent.org/beps/bep_0005.html
    if nodes is not None:
        for node in nodes:
            torrent.add_node(*node)
    # HTTP seeding
    # http://www.bittorrent.org/beps/bep_0017.html
    if http_seeds is not None:
        for http_seed in http_seeds:
            torrent.add_http_seed(http_seed)

    # Web seeding
    # http://www.bittorrent.org/beps/bep_0019.html
    if len(file_path_list) == 1 and url_list is not None:
        for url_lentry in url_list:
            torrent.add_url_seed(url_lentry)

    # read the files and calculate the hashes
    lt.set_piece_hashes(torrent, str(export_dir))

    t1 = torrent.generate()
    torrent_bytes = lt.bencode(t1)

    return {
        "success": True,
        "base_dir": base_dir,
        "atp": lt.load_torrent_buffer(torrent_bytes),  # type: ignore[attr-defined]
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
