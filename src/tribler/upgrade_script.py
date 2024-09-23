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
from pony.orm import db_session

if TYPE_CHECKING:
    from tribler.tribler_config import TriblerConfigManager

FROM: str = "7.14"
TO: str = "8.0"

# ruff: noqa: N802,RUF015,W291


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


def _inject_StatementOp(abs_src_db: str, abs_dst_db: str) -> None:
    """
    Import old StatementOp entries.
    """
    src_con = sqlite3.connect(abs_src_db)
    output = list(src_con.execute("""SELECT SubjectResource.name, SubjectResource.type, ObjectResource.name,
ObjectResource.type, Statement.added_count, Statement.removed_count, Statement.local_operation, Peer.public_key,
Peer.added_at, StatementOp.operation, StatementOp.clock, StatementOp.signature, StatementOp.updated_at,
StatementOp.auto_generated
FROM StatementOp
INNER JOIN Peer ON StatementOp.peer=Peer.id
INNER JOIN Statement ON StatementOp.statement=Statement.id
INNER JOIN Resource AS SubjectResource ON Statement.subject=SubjectResource.id
INNER JOIN Resource AS ObjectResource ON Statement.object=ObjectResource.id
;"""))
    src_con.close()

    dst_con = sqlite3.connect(abs_dst_db)
    with db_session:
        for (subject_name, subject_type,
             object_name, object_type,
             stmt_added_count, stmt_removed_count, stmt_local_operation,
             peer_public_key, peer_added_at,
             stmtop_operation, stmtop_clock, stmtop_signature, stmtop_updated_at, stmtop_auto_generated) in output:
            dst_con.execute("BEGIN")
            try:
                # Insert subject
                results = list(dst_con.execute("SELECT id FROM Resource WHERE name=? AND type=?",
                                               (subject_name, subject_type)))
                if not results:
                    cursor = dst_con.execute("INSERT INTO Resource "
                                             "VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Resource), ?, ?)",
                                             (subject_name, subject_type))
                    results = [(cursor.lastrowid, )]
                subject_id, = results[0]

                # Insert object
                results = list(
                    dst_con.execute("SELECT id FROM Resource WHERE name=? AND type=?", (object_name, object_type)))
                if not results:
                    cursor = dst_con.execute(
                        "INSERT INTO Resource VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Resource), ?, ?)",
                        (object_name, object_type)
                    )
                    results = [(cursor.lastrowid, )]
                object_id, = results[0]

                # Insert statement
                results = list(dst_con.execute("SELECT id FROM Statement WHERE object=? AND subject=?",
                                               (object_id, subject_id)))
                if not results:
                    cursor = dst_con.execute(
                        "INSERT INTO Statement VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Statement), ?, ?, ?, ?, ?)",
                        (subject_id, object_id, stmt_added_count, stmt_removed_count, stmt_local_operation)
                    )
                    results = [(cursor.lastrowid, )]
                statement_id, = results[0]

                # Insert peer
                results = list(
                    dst_con.execute("SELECT id, added_at FROM Peer WHERE public_key=?", (peer_public_key, )))
                if results and results[0][1] >= peer_added_at:
                    dst_con.execute("UPDATE Peer SET added_at=? WHERE public_key=?", (peer_added_at, peer_public_key))
                    results = [(results[0][0],)]
                elif not results:
                    cursor = dst_con.execute(
                        "INSERT INTO Peer VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM Peer), ?, ?)",
                        (peer_public_key, peer_added_at)
                    )
                    results = [(cursor.lastrowid, )]
                else:
                    results = [(results[0][0], )]
                peer_id, = results[0]

                # Insert statement op
                results = list(dst_con.execute("SELECT id FROM StatementOp WHERE statement=? AND peer=?",
                                               (statement_id, peer_id)))
                if not results:
                    dst_con.execute(
                        "INSERT INTO StatementOp VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM StatementOp), "
                        "?, ?, ?, ?, ?, ?, ?)",
                        (statement_id, peer_id, stmtop_operation, stmtop_clock, stmtop_signature, stmtop_updated_at,
                         stmtop_auto_generated))

                dst_con.execute("COMMIT")
            except sqlite3.DatabaseError as e:
                dst_con.execute("ROLLBACK")
                logging.exception(e)
        dst_con.commit()
    dst_con.close()


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

    dst_con = sqlite3.connect(abs_dst_db)
    with db_session:
        for (infohash, size, torrent_date, tracker_info, title, tags, metadata_type, reserved_flags,
             origin_id, public_key, id_, timestamp, signature, added_on, status, xxx, tag_processor_version,
             seeders, leechers, last_check, self_checked, has_data) in output:
            dst_con.execute("BEGIN")
            try:
                # Insert subject
                results = list(dst_con.execute("SELECT rowid FROM TorrentState WHERE infohash=?", (infohash, )))
                if not results:
                    cursor = dst_con.execute("INSERT INTO TorrentState "
                                             "VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM TorrentState), "
                                             "?, ?, ?, ?, ?, ?)",
                                             (infohash, seeders, leechers, last_check, self_checked, has_data))
                    results = [(cursor.lastrowid, )]
                health_id, = results[0]

                # Insert channel ChannelNode
                results = list(dst_con.execute("SELECT rowid FROM ChannelNode WHERE public_key=? AND id_=?",
                                               (public_key, id_)))
                if not results:
                    dst_con.execute(
                        "INSERT INTO ChannelNode VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM ChannelNode), "
                        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (infohash, size, torrent_date, tracker_info, title, tags, metadata_type, reserved_flags,
                         origin_id, public_key, id_, timestamp, signature, added_on, status, xxx, health_id,
                         tag_processor_version))

                dst_con.execute("COMMIT")
            except sqlite3.DatabaseError as e:
                dst_con.execute("ROLLBACK")
                logging.exception(e)
        dst_con.commit()
    dst_con.close()


def _inject_TrackerState(abs_src_db: str, abs_dst_db: str) -> None:
    """
    Import old TrackerState entries.
    """
    src_con = sqlite3.connect(abs_src_db)
    output = list(src_con.execute("SELECT url, last_check, alive, failures FROM TrackerState;"))
    src_con.close()

    dst_con = sqlite3.connect(abs_dst_db)
    with db_session:
        for (url, last_check, alive, failures) in output:
            dst_con.execute("BEGIN")
            try:
                results = list(dst_con.execute("SELECT rowid, last_check, alive, failures FROM TrackerState WHERE url=?", (url, )))
                if results:
                    tracker_id, n_last_check, n_alive, n_failures = results[0]
                    s_last_check = max(n_last_check, last_check)
                    s_alive = alive if last_check > n_last_check else n_alive
                    s_failures = int(failures) + int(n_failures)
                    dst_con.execute(
                        "UPDATE TrackerState SET last_check=?, alive=?, failures=? WHERE rowid=?",
                        (s_last_check, s_alive, s_failures, tracker_id))
                else:
                    dst_con.execute(
                        "INSERT INTO TrackerState VALUES ((SELECT COALESCE(MAX(rowid),0)+1 FROM TrackerState), "
                        "?, ?, ?, ?)",
                        (url, last_check, alive, failures))

                dst_con.execute("COMMIT")
            except sqlite3.DatabaseError as e:
                dst_con.execute("ROLLBACK")
                logging.exception(e)
        dst_con.commit()
    dst_con.close()


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

    dst_con = sqlite3.connect(abs_dst_db)
    with db_session:
        for (infohash, url) in output:
            dst_con.execute("BEGIN")
            try:
                results = list(dst_con.execute("""SELECT TorrentState.infohash, TrackerState.url
FROM TorrentState_TrackerState
INNER JOIN TorrentState ON TorrentState_TrackerState.torrentstate=TorrentState.rowid
INNER JOIN TrackerState ON TorrentState_TrackerState.trackerstate=TrackerState.rowid
WHERE TorrentState.infohash=? AND TrackerState.url=?
;""", (infohash, url)))
                if not results:
                    # Note: both the tracker and torrent state should've been imported already
                    torrent_state, = list(dst_con.execute("SELECT rowid FROM TorrentState WHERE infohash=?",
                                                          (infohash,)))[0]
                    tracker_state, = list(dst_con.execute("SELECT rowid FROM TrackerState WHERE url=?",
                                                          (url,)))[0]
                    dst_con.execute("INSERT INTO TorrentState_TrackerState VALUES (?, ?)",
                                    (torrent_state, tracker_state))

                dst_con.execute("COMMIT")
            except sqlite3.DatabaseError as e:
                dst_con.execute("ROLLBACK")
                logging.exception(e)
        dst_con.commit()
    dst_con.close()


def _inject_7_14_tables(src_db: str, dst_db: str, db_format: str) -> None:
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
    assert db_format in ["tribler.db", "metadata.db"]

    abs_src_db = os.path.abspath(src_db)
    abs_dst_db = os.path.abspath(dst_db)

    if db_format == "tribler.db":
        _inject_StatementOp(abs_src_db, abs_dst_db)
    else:
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
    os.makedirs(os.path.join(destination, "dlcheckpoints"), exist_ok=True)
    for checkpoint in os.listdir(os.path.join(source, "dlcheckpoints")):
        _copy_if_not_exist(os.path.join(source, "dlcheckpoints", checkpoint),
                           os.path.join(destination, "dlcheckpoints", checkpoint))

    # Step 3: Copy tribler db.
    os.makedirs(os.path.join(destination, "sqlite"), exist_ok=True)
    _inject_7_14_tables(os.path.join(source, "sqlite", "tribler.db"),
                        os.path.join(destination, "sqlite", "tribler.db"),
                        "tribler.db")

    # Step 4: Copy metadata db.
    _inject_7_14_tables(os.path.join(source, "sqlite", "metadata.db"),
                        os.path.join(destination, "sqlite", "metadata.db"),
                        "metadata.db")

    # Step 5: Signal that our upgrade is done.
    with open(os.path.join(config.get_version_state_dir(), ".upgraded"), "a"):
        pass
