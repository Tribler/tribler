from __future__ import annotations

import typing
from collections import defaultdict
from enum import Enum
from typing import Callable

from ipv8.messaging.anonymization.tunnel import Circuit


class Desc(typing.NamedTuple):
    """
    A Notification callback descriptor.
    """

    name: str
    fields: list[str]
    types: list[tuple[type, ...] | type]


class Notification(Enum):
    """
    All possible global events that happen in Tribler.
    """

    torrent_finished = Desc("torrent_finished", ["infohash", "name", "hidden"], [str, str, bool])
    torrent_status_changed = Desc("torrent_status_changed", ["infohash", "status"], [str, str])
    tribler_shutdown_state = Desc("tribler_shutdown_state", ["state"], [str])
    tribler_new_version = Desc("tribler_new_version", ["version"], [str])
    remote_query_results = Desc("remote_query_results", ["query", "results", "uuid", "peer"], [str, list, str, str])
    local_query_results = Desc("local_query_results", ["query", "results"], [str, list])
    circuit_removed = Desc("circuit_removed", ["circuit", "additional_info"], [str, Circuit])
    tunnel_removed = Desc("tunnel_removed", ["circuit_id", "bytes_up", "bytes_down", "uptime", "additional_info"],
                          [int, int, int, float, str])
    torrent_health_updated = Desc("torrent_health_updated",
                                  ["infohash", "num_seeders", "num_leechers", "last_tracker_check", "health"],
                                  [str, int, int, int, str])
    low_space = Desc("low_space", ["disk_usage_data"], [dict])
    events_start = Desc("events_start", ["public_key", "version"], [str, str])
    tribler_exception = Desc("tribler_exception", ["error"], [dict])
    content_discovery_community_unknown_torrent_added = Desc("content_discovery_community_unknown_torrent_added",
                                                             [], [])
    report_config_error = Desc("report_config_error", ["error"], [str])
    peer_disconnected = Desc("peer_disconnected", ["peer_id"], [bytes])
    tribler_torrent_peer_update = Desc("tribler_torrent_peer_update", ["peer_id", "infohash", "balance"],
                                       [bytes, bytes, int])
    torrent_metadata_added = Desc("torrent_metadata_added", ["metadata"], [dict])
    new_torrent_metadata_created = Desc("new_torrent_metadata_created", ["infohash", "title"],
                                        [(bytes, type(None)), (str, type(None))])


class Notifier:
    """
    The class responsible for managing and calling observers of global Tribler events.
    """

    def __init__(self) -> None:
        """
        Create a new notifier.
        """
        self.observers: dict[Notification, list[Callable[..., None]]] = defaultdict(list)
        self.delegates: set[Callable[..., None]] = set()

    def add(self, topic: Notification, observer: Callable[..., None]) -> None:
        """
        Add an observer for the given Notification type.
        """
        self.observers[topic].append(observer)

    def notify(self, topic: Notification | str, /, **kwargs) -> None:
        """
        Notify all observers that have subscribed to the given topic.
        """
        notification = getattr(Notification, topic) if isinstance(topic, str) else topic
        topic_name, args, types = notification.value
        if set(args) ^ set(kwargs.keys()):
            message = f"{topic_name} expecting arguments {args} (of types {types}) but received {kwargs}"
            raise ValueError(message)
        for observer in self.observers[notification]:
            observer(**kwargs)
        for delegate in self.delegates:
            delegate(notification, **kwargs)
