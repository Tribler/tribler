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
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

from configobj import ConfigObj
from pony.orm import Database, OperationalError, db_session

if TYPE_CHECKING:
    from collections.abc import Generator

    from tribler.tribler_config import TriblerConfigManager

FROM: str = "7.14"
TO: str = "8.0"

# ruff: noqa: B007,C901,F841,N802,RUF015,W291


def batched(results: list, n: int = 1) -> Generator[list]:
    """
    Backport for ``itertools.batched()``.
    """
    for start in islice(range(len(results)), None, None, 2):
        yield results[start : (start+n)]


def _copy_if_not_exist(src: str, dst: str) -> None:
    """
    Copy a file if it does not exist.
    """
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy(src, dst)


def _copy_if_exists(src: ConfigObj, src_path: str, dst: TriblerConfigManager, dst_path: str, conversion: type) -> None:
    """
    Check if the src path is set and copy it into the dst if it is.
    """
    out = src
    for part in Path(src_path).parts:
        if part in out:
            out = out.get(part)
        else:
            return
    dst.set(dst_path, conversion(out))


def _import_7_14_settings(src: str, dst: TriblerConfigManager) -> None:
    """
    Read the file at the source path and import its settings.
    """
    old = ConfigObj(src, encoding="utf-8")
    _copy_if_exists(old, "api/key", dst, "api/key", str)
    _copy_if_exists(old, "api/http_enabled", dst, "api/http_enabled", bool)
    _copy_if_exists(old, "api/https_enabled", dst, "api/https_enabled", bool)
    _copy_if_exists(old, "ipv8/statistics", dst, "statistics", bool)
    _copy_if_exists(old, "libtorrent/port", dst, "libtorrent/port", int)
    _copy_if_exists(old, "libtorrent/proxy_type", dst, "libtorrent/proxy_type", int)
    _copy_if_exists(old, "libtorrent/proxy_server", dst, "libtorrent/proxy_server", str)
    _copy_if_exists(old, "libtorrent/proxy_auth", dst, "libtorrent/proxy_auth", str)
    _copy_if_exists(old, "libtorrent/max_connections_download", dst, "libtorrent/max_connections_download", int)
    _copy_if_exists(old, "libtorrent/max_download_rate", dst, "libtorrent/max_download_rate", int)
    _copy_if_exists(old, "libtorrent/max_upload_rate", dst, "libtorrent/max_upload_rate", int)
    _copy_if_exists(old, "libtorrent/utp", dst, "libtorrent/utp", bool)
    _copy_if_exists(old, "libtorrent/dht", dst, "libtorrent/dht", bool)
    _copy_if_exists(old, "libtorrent/dht_readiness_timeout", dst, "libtorrent/dht_readiness_timeout", int)
    _copy_if_exists(old, "libtorrent/upnp", dst, "libtorrent/upnp", bool)
    _copy_if_exists(old, "libtorrent/natpmp", dst, "libtorrent/natpmp", bool)
    _copy_if_exists(old, "libtorrent/lsd", dst, "libtorrent/lsd", bool)
    _copy_if_exists(old, "download_defaults/anonymity_enabled",
                    dst, "libtorrent/download_defaults/anonymity_enabled", bool)
    _copy_if_exists(old, "download_defaults/number_hops", dst, "libtorrent/download_defaults/number_hops", int)
    _copy_if_exists(old, "download_defaults/safeseeding_enabled",
                    dst, "libtorrent/download_defaults/safeseeding_enabled", bool)
    _copy_if_exists(old, "download_defaults/saveas", dst, "libtorrent/download_defaults/saveas", str)
    _copy_if_exists(old, "download_defaults/seeding_mode", dst, "libtorrent/download_defaults/seeding_mode", str)
    _copy_if_exists(old, "download_defaults/seeding_ratio", dst, "libtorrent/download_defaults/seeding_ratio", float)
    _copy_if_exists(old, "download_defaults/seeding_time", dst, "libtorrent/download_defaults/seeding_time", float)
    _copy_if_exists(old, "download_defaults/channel_download",
                    dst, "libtorrent/download_defaults/channel_download", bool)
    _copy_if_exists(old, "download_defaults/add_download_to_channel",
                    dst, "libtorrent/download_defaults/add_download_to_channel", bool)
    _copy_if_exists(old, "popularity_community/enabled", dst, "content_discovery_community/enabled", bool)
    _copy_if_exists(old, "torrent_checking/enabled", dst, "torrent_checker/enabled", bool)
    _copy_if_exists(old, "tunnel_community/enabled", dst, "tunnel_community/enabled", bool)
    _copy_if_exists(old, "tunnel_community/min_circuits", dst, "tunnel_community/min_circuits", int)
    _copy_if_exists(old, "tunnel_community/max_circuits", dst, "tunnel_community/max_circuits", int)


@db_session(retry=3)
def _inject_StatementOp_inner(db: Database, batch: list) -> None:
    """
    The inner injection script to write old StatementOp info into the current database.
    """
    for (subject_name, subject_type,
         object_name, object_type,
         stmt_added_count, stmt_removed_count, stmt_local_operation,
         peer_public_key, peer_added_at,
         stmtop_operation, stmtop_clock, stmtop_signature, stmtop_updated_at, stmtop_auto_generated) in batch:
        # Insert subject
        results = list(db.execute("SELECT id FROM Resource WHERE name=$subject_name AND type=$subject_type",
                                  globals(), locals()))
        if not results:
            cursor = db.execute("INSERT INTO Resource "
                                "VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Resource), $subject_name, "
                                "$subject_type)",
                                globals(), locals())
            results = [(cursor.lastrowid,)]
        subject_id, = results[0]

        # Insert object
        results = list(
            db.execute("SELECT id FROM Resource WHERE name=$object_name AND type=$object_type",
                       globals(), locals()))
        if not results:
            cursor = db.execute(
                "INSERT INTO Resource VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Resource), $object_name, "
                "$object_type)",
                globals(), locals()
            )
            results = [(cursor.lastrowid,)]
        object_id, = results[0]

        # Insert statement
        results = list(db.execute(
            "SELECT id FROM Statement WHERE object=$object_id AND subject=$subject_id",
            globals(), locals()))
        if not results:
            cursor = db.execute(
                "INSERT INTO Statement VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Statement), $subject_id, "
                "$object_id, $stmt_added_count, $stmt_removed_count, $stmt_local_operation)",
                globals(), locals()
            )
            results = [(cursor.lastrowid,)]
        statement_id, = results[0]

        # Insert peer
        results = list(
            db.execute("SELECT id, added_at FROM Peer WHERE public_key=$peer_public_key",
                       globals(), locals()))
        if results and results[0][1] >= peer_added_at:
            db.execute("UPDATE Peer SET added_at=$peer_added_at WHERE public_key=$peer_public_key",
                       globals(), locals())
            results = [(results[0][0],)]
        elif not results:
            cursor = db.execute(
                "INSERT INTO Peer VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Peer), $peer_public_key, "
                "$peer_added_at)",
                globals(), locals()
            )
            results = [(cursor.lastrowid,)]
        else:
            results = [(results[0][0],)]
        peer_id, = results[0]

        # Insert statement op
        results = list(db.execute("SELECT id FROM StatementOp WHERE statement=$statement_id AND "
                                  "peer=$peer_id",
                                  globals(), locals()))
        if not results:
            db.execute(
                "INSERT INTO StatementOp VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM StatementOp), "
                "$statement_id, $peer_id, $stmtop_operation, $stmtop_clock, $stmtop_signature, "
                "$stmtop_updated_at, $stmtop_auto_generated)",
                globals(), locals())


@db_session(retry=3)
def _inject_ChannelNode_inner(db: Database, batch: list) -> None:
    """
    The inner injection script to write old ChannelNode info into the current database.
    """
    for (infohash, size, torrent_date, tracker_info, title, tags, metadata_type, reserved_flags,
         origin_id, public_key, id_, timestamp, signature, added_on, status, xxx, tag_processor_version,
         seeders, leechers, last_check, self_checked, has_data) in batch:
        # Insert subject
        results = list(db.execute("SELECT rowid FROM TorrentState WHERE infohash=$infohash",
                                  globals(), locals()))
        if not results:
            cursor = db.execute("INSERT INTO TorrentState "
                                "VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM TorrentState), "
                                "$infohash, $seeders, $leechers, $last_check, $self_checked, $has_data)",
                                globals(), locals())
            results = [(cursor.lastrowid,)]
        health_id, = results[0]

        # Insert channel ChannelNode
        results = list(db.execute("SELECT rowid FROM ChannelNode WHERE public_key=$public_key AND id_=$id_",
                                  globals(), locals()))
        if not results:
            db.execute(
                "INSERT INTO ChannelNode VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM ChannelNode), "
                "$infohash, $size, $torrent_date, $tracker_info, $title, $tags, $metadata_type, "
                "$reserved_flags, $origin_id, $public_key, $id_, $timestamp, $signature, $added_on, "
                "$status, $xxx, $health_id, $tag_processor_version)",
                globals(), locals())


def _inject_ChannelNode(abs_src_db: str, abs_dst_db: str) -> None:
    """
    Import old ChannelNode entries.
    """
    src_con = sqlite3.connect(abs_src_db)
    output = list(src_con.execute("""SELECT ChannelNode.infohash, ChannelNode.size, ChannelNode.torrent_date, 
ChannelNode.tracker_info, ChannelNode.title, ChannelNode.tags, ChannelNode.metadata_type, ChannelNode.reserved_flags, 
ChannelNode.origin_id, ChannelNode.public_key, ChannelNode.id_, ChannelNode.timestamp, ChannelNode.signature, 
ChannelNode.added_on, ChannelNode.status, ChannelNode.xxx, ChannelNode.tag_processor_version, TorrentState.seeders, 
TorrentState.leechers, TorrentState.last_check, TorrentState.self_checked, TorrentState.has_data
FROM ChannelNode
INNER JOIN TorrentState ON ChannelNode.health=TorrentState.rowid
;"""))
    src_con.close()

    db = Database()
    db.bind(provider="sqlite", filename=abs_dst_db)
    for batch in batched(output, n=20):
        try:
            _inject_ChannelNode_inner(db, batch)
        except OperationalError as e:
            logging.exception(e)
    try:
        db.disconnect()
    except OperationalError as e:
        logging.exception(e)


@db_session(retry=3)
def _inject_TrackerState_inner(db: Database, batch: list) -> None:
    """
    The inner injection script to write old TrackerState info into the current database.
    """
    for (url, last_check, alive, failures) in batch:
        results = list(db.execute("SELECT rowid, last_check, alive, failures FROM TrackerState WHERE "
                                  "url=$url",
                                  globals(), locals()))
        if results:
            tracker_id, n_last_check, n_alive, n_failures = results[0]
            s_last_check = max(n_last_check, last_check)
            s_alive = alive if last_check > n_last_check else n_alive
            s_failures = int(failures) + int(n_failures)
            db.execute(
                "UPDATE TrackerState SET last_check=$s_last_check, alive=$s_alive, failures=$s_failures "
                "WHERE rowid=$tracker_id",
                globals(), locals())
        else:
            db.execute(
                "INSERT INTO TrackerState VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM TrackerState), "
                "$url, $last_check, $alive, $failures)",
                globals(), locals())


def _inject_TrackerState(abs_src_db: str, abs_dst_db: str) -> None:
    """
    Import old TrackerState entries.
    """
    src_con = sqlite3.connect(abs_src_db)
    output = list(src_con.execute("SELECT url, last_check, alive, failures FROM TrackerState;"))
    src_con.close()

    db = Database()
    db.bind(provider="sqlite", filename=abs_dst_db)
    for batch in batched(output, n=20):
        try:
            _inject_TrackerState_inner(db, batch)
        except OperationalError as e:
            logging.exception(e)
    try:
        db.disconnect()
    except OperationalError as e:
        logging.exception(e)


@db_session(retry=3)
def _inject_TorrentState_TrackerState_inner(db: Database, batch: list) -> None:
    """
    The inner injection script to write old TorrentState info into the current database.
    """
    for (infohash, url) in batch:
        results = list(db.execute("""SELECT TorrentState.infohash, TrackerState.url
FROM TorrentState_TrackerState
INNER JOIN TorrentState ON TorrentState_TrackerState.torrentstate=TorrentState.rowid
INNER JOIN TrackerState ON TorrentState_TrackerState.trackerstate=TrackerState.rowid
WHERE TorrentState.infohash=$infohash AND TrackerState.url=$url
;""", globals(), locals()))
        if not results:
            # Note: both the tracker and torrent state should've been imported already
            torrent_states = list(db.execute("SELECT rowid FROM TorrentState WHERE infohash=$infohash",
                                             globals(), locals()))
            tracker_states = list(db.execute("SELECT rowid FROM TrackerState WHERE url=$url",
                                             globals(), locals()))
            if not torrent_states:
                logging.warning("Torrent state for %s disappeared mid-upgrade!", infohash)
                continue
            if not tracker_states:
                logging.warning("Tracker state for %s disappeared mid-upgrade!", url)
                continue
            torrent_state, = torrent_states[0]
            tracker_state, = tracker_states[0]
            db.execute("INSERT INTO TorrentState_TrackerState VALUES ($torrent_state, $tracker_state)",
                       globals(), locals())


def _inject_TorrentState_TrackerState(abs_src_db: str, abs_dst_db: str) -> None:
    """
    Import old TorrentState_TrackerState entries.
    """
    src_con = sqlite3.connect(abs_src_db)
    output = list(src_con.execute("""SELECT TorrentState.infohash, TrackerState.url
FROM TorrentState_TrackerState
INNER JOIN TorrentState ON TorrentState_TrackerState.torrentstate=TorrentState.rowid
INNER JOIN TrackerState ON TorrentState_TrackerState.trackerstate=TrackerState.rowid
;"""))
    src_con.close()

    db = Database()
    db.bind(provider="sqlite", filename=abs_dst_db)
    for batch in batched(output, n=20):
        try:
            _inject_TorrentState_TrackerState_inner(db, batch)
        except OperationalError as e:
            logging.exception(e)
    try:
        db.disconnect()
    except OperationalError as e:
        logging.exception(e)


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

    abs_src_db = os.path.abspath(src_db)
    abs_dst_db = os.path.abspath(dst_db)

    _inject_ChannelNode(abs_src_db, abs_dst_db)
    _inject_TrackerState(abs_src_db, abs_dst_db)
    _inject_TorrentState_TrackerState(abs_src_db, abs_dst_db)


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
    parent_directory = os.path.dirname(destination)  # Starting from 8.0.4 this is no longer versioned information
    os.makedirs(os.path.join(parent_directory, "dlcheckpoints"), exist_ok=True)
    for checkpoint in os.listdir(os.path.join(source, "dlcheckpoints")):
        _copy_if_not_exist(os.path.join(source, "dlcheckpoints", checkpoint),
                           os.path.join(parent_directory, "dlcheckpoints", checkpoint))

    # Step 3: Copy metadata db.
    _inject_7_14_tables(os.path.join(source, "sqlite", "metadata.db"),
                        os.path.join(destination, "sqlite", "metadata.db"))

    # Step 4: Signal that our upgrade is done.
    with open(os.path.join(config.get_version_state_dir(), ".upgraded"), "a"):
        pass
