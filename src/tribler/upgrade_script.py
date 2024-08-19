"""
UPDATE THIS FILE WHENEVER A NEW VERSION GETS RELEASED.

Checklist:

 - Have you changed ``FROM`` to the previous version?
 - Have you changed ``TO`` to the current version?
 - Have you changed ``upgrade()`` to perform the upgrade?
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from configobj import ConfigObj

if TYPE_CHECKING:
    from tribler.tribler_config import TriblerConfigManager

FROM: str = "7.14"
TO: str = "8.0"


def _copy_if_not_exist(src: str, dst: str) -> None:
    """
    Copy a file if it does not exist.
    """
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy(src, dst)


def _copy_if_exists(src: ConfigObj, src_path: str, dst: TriblerConfigManager, dst_path: str) -> None:
    """
    Check if the src path is set and copy it into the dst if it is.
    """
    out = src
    for part in Path(src_path).parts:
        if part in out:
            out = out.get(part)
        else:
            return
    dst.set(dst_path, out)


def _import_7_14_settings(src: str, dst: TriblerConfigManager) -> None:
    """
    Read the file at the source path and import its settings.
    """
    old = ConfigObj(src)
    _copy_if_exists(old, "api/key", dst, "api/key")
    _copy_if_exists(old, "api/http_enabled", dst, "api/http_enabled")
    _copy_if_exists(old, "api/https_enabled", dst, "api/https_enabled")
    _copy_if_exists(old, "ipv8/statistics", dst, "statistics")
    _copy_if_exists(old, "libtorrent/port", dst, "libtorrent/port")
    _copy_if_exists(old, "libtorrent/proxy_type", dst, "libtorrent/proxy_type")
    _copy_if_exists(old, "libtorrent/proxy_server", dst, "libtorrent/proxy_server")
    _copy_if_exists(old, "libtorrent/proxy_auth", dst, "libtorrent/proxy_auth")
    _copy_if_exists(old, "libtorrent/max_connections_download", dst, "libtorrent/max_connections_download")
    _copy_if_exists(old, "libtorrent/max_download_rate", dst, "libtorrent/max_download_rate")
    _copy_if_exists(old, "libtorrent/max_upload_rate", dst, "libtorrent/max_upload_rate")
    _copy_if_exists(old, "libtorrent/utp", dst, "libtorrent/utp")
    _copy_if_exists(old, "libtorrent/dht", dst, "libtorrent/dht")
    _copy_if_exists(old, "libtorrent/dht_readiness_timeout", dst, "libtorrent/dht_readiness_timeout")
    _copy_if_exists(old, "libtorrent/upnp", dst, "libtorrent/upnp")
    _copy_if_exists(old, "libtorrent/natpmp", dst, "libtorrent/natpmp")
    _copy_if_exists(old, "libtorrent/lsd", dst, "libtorrent/lsd")
    _copy_if_exists(old, "download_defaults/anonymity_enabled", dst, "libtorrent/download_defaults/anonymity_enabled")
    _copy_if_exists(old, "download_defaults/number_hops", dst, "libtorrent/download_defaults/number_hops")
    _copy_if_exists(old, "download_defaults/safeseeding_enabled",
                    dst, "libtorrent/download_defaults/safeseeding_enabled")
    _copy_if_exists(old, "download_defaults/saveas", dst, "libtorrent/download_defaults/saveas")
    _copy_if_exists(old, "download_defaults/seeding_mode", dst, "libtorrent/download_defaults/seeding_mode")
    _copy_if_exists(old, "download_defaults/seeding_ratio", dst, "libtorrent/download_defaults/seeding_ratio")
    _copy_if_exists(old, "download_defaults/seeding_time", dst, "libtorrent/download_defaults/seeding_time")
    _copy_if_exists(old, "download_defaults/channel_download", dst, "libtorrent/download_defaults/channel_download")
    _copy_if_exists(old, "download_defaults/add_download_to_channel",
                    dst, "libtorrent/download_defaults/add_download_to_channel")
    _copy_if_exists(old, "popularity_community/enabled", dst, "content_discovery_community/enabled")
    _copy_if_exists(old, "torrent_checking/enabled", dst, "torrent_checker/enabled")
    _copy_if_exists(old, "tunnel_community/enabled", dst, "tunnel_community/enabled")
    _copy_if_exists(old, "tunnel_community/min_circuits", dst, "tunnel_community/min_circuits")
    _copy_if_exists(old, "tunnel_community/max_circuits", dst, "tunnel_community/max_circuits")


def _inject_7_14_tables(src_db: str, dst_db: str) -> None:
    """
    Fetch data from the old database and attempt to insert it into a new one.
    """
    # If the src does not exist, there is nothing to copy.
    if not os.path.exists(src_db):
        return

    # If the dst does not exist, simply copy the src over.
    if not os.path.exists(dst_db):
        shutil.copy(src_db, dst_db)
        return

    # If they both exist, we have to inject data.
    src_con = sqlite3.connect(os.path.abspath(src_db))
    insert_script = list(src_con.iterdump())
    src_con.close()

    from pony.orm import db_session
    dst_con = sqlite3.connect(os.path.abspath(dst_db))
    with db_session:
        for line in insert_script:
            try:
                dst_con.execute(line)
            except sqlite3.DatabaseError as e:
                logging.exception(e)
        dst_con.commit()  # This should be part of the dump already but just to be sure.
    dst_con.close()


def upgrade(config: TriblerConfigManager, source: str, destination: str) -> None:
    """
    Perform the upgrade from the previous version to the next version.
    When complete, write a ".upgraded" file to the destination path.

    The files in ``source`` should be expected to be in the FROM format.
    The files in ``destination`` should be expected to be in the TO format.

    Make sure to deal with corruption and/or missing files!
    """
    # Step 1: import settings
    os.makedirs(destination, exist_ok=True)
    if os.path.exists(os.path.join(source, "triblerd.conf")):
        _import_7_14_settings(os.path.join(source, "triblerd.conf"), config)
    config.write()

    # Step 2: copy downloads
    os.makedirs(os.path.join(destination, "dlcheckpoints"), exist_ok=True)
    for checkpoint in os.listdir(os.path.join(source, "dlcheckpoints")):
        _copy_if_not_exist(os.path.join(source, "dlcheckpoints", checkpoint),
                           os.path.join(destination, "dlcheckpoints", checkpoint))

    # Step 3: Copy tribler db.
    os.makedirs(os.path.join(destination, "sqlite"), exist_ok=True)
    _inject_7_14_tables(os.path.join(source, "sqlite", "tribler.db"),
                        os.path.join(destination, "sqlite", "tribler.db"))

    # Step 4: Copy metadata db.
    _inject_7_14_tables(os.path.join(source, "sqlite", "metadata.db"),
                        os.path.join(destination, "sqlite", "metadata.db"))

    # Step 5: Signal that our upgrade is done.
    with open(os.path.join(config.get_version_state_dir(), ".upgraded"), "a"):
        pass
