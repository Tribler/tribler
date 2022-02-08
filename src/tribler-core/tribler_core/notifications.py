from typing import Optional

from ipv8.messaging.anonymization.tunnel import Circuit


# pylint: disable=unused-argument


def torrent_finished(infohash: str, name: str, hidden: bool):
    # A torrent has finished downloading. Contains the infohash and the name of the torrent
    ...


def tribler_shutdown_state(state: str):
    # Tribler is going to shutdown
    ...


def tribler_new_version(version: str):
    # A new version of Tribler is available
    ...


def channel_discovered(data: dict):
    # Tribler has discovered a new channel. Contains the channel data
    ...


def remote_query_results(data: dict):
    # Remote GigaChannel search results were received by Tribler. Contains received entries
    ...


def circuit_removed(circuit: Circuit, additional_info: str):
    # Tribler tunnel circuit has been removed (notification to Core)
    ...


def tunnel_removed(circuit_id: int, bytes_up: int, bytes_down: int, uptime: float, additional_info: str = ''):
    # Tribler tunnel circuit has been removed (notification to GUI)
    ...


def watch_folder_corrupt_file(file_name: str):
    # A corrupt .torrent file in the watch folder is found. Contains the name of the corrupt torrent file
    ...


def channel_entity_updated(channel_update_dict: dict):
    # Information about some torrent has been updated (e.g. health). Contains updated torrent data
    ...


def low_space(disk_usage_data: dict):
    # Tribler is low on disk space for storing torrents
    ...


def events_start(public_key: str, version: str):
    ...


def tribler_exception(error: dict):
    ...


def popularity_community_unknown_torrent_added():
    ...


def report_config_error(error):
    # Report config error on startup
    ...


def peer_disconnected(peer_id: bytes):
    ...


def tribler_torrent_peer_update(peer_id: bytes, infohash: bytes, balance: int):
    ...


def torrent_metadata_added(metadata: dict):
    ...


def new_torrent_metadata_created(infohash: Optional[bytes] = None, title: Optional[str] = None):
    ...
