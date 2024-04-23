from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pony import orm

from tribler.core.libtorrent.trackers import MalformedTrackerURLException, get_uniformed_tracker_url

if TYPE_CHECKING:
    from dataclasses import dataclass

    from pony.orm import Database

    from tribler.core.database.orm_bindings.torrent_state import TorrentState


    @dataclass
    class TrackerState:
        """
        Database type for the state of a tracker.
        """

        rowid: int
        url: str
        last_check: int | None
        alive: bool | None
        torrents: set[TorrentState]
        failures: int | None

        def __init__(self, url: str) -> None: ...  # noqa: D107

        @staticmethod
        def get(url: str) -> TrackerState | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(url: str) -> TrackerState | None: ...  # noqa: D102


def define_binding(db: Database) -> type[TrackerState]:
    """
    Define the tracker state binding.
    """

    class TrackerState(db.Entity):
        """
        This ORM class holds information about torrent trackers that TorrentChecker got while checking
        torrents' health.
        """

        rowid = orm.PrimaryKey(int, auto=True)
        url = orm.Required(str, unique=True)
        last_check = orm.Optional(int, size=64, default=0)
        alive = orm.Optional(bool, default=True)
        torrents = orm.Set('TorrentState', reverse='trackers')
        failures = orm.Optional(int, size=32, default=0)

        def __init__(self, *args: Any, **kwargs) -> None:  # noqa: ANN401
            # Sanitize and canonicalize the tracker URL
            sanitized = get_uniformed_tracker_url(kwargs['url'])
            if sanitized:
                kwargs['url'] = sanitized
            else:
                msg = f"Could not canonicalize tracker URL ({kwargs['url']})"
                raise MalformedTrackerURLException(msg)

            super().__init__(*args, **kwargs)

    return TrackerState
