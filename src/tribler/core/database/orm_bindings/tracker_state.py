from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pony import orm

from tribler.core.libtorrent.trackers import MalformedTrackerURLException, get_uniformed_tracker_url

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
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
        last_check: int
        alive: bool
        torrents: set[TorrentState]
        failures: int

        def __init__(self, rowid: int | None = None, url: str | None = None,  # noqa: D107
                     last_check: int | None = None, alive: bool | None = None,
                     torrents: set[TorrentState] | None = None, failures: int | None = None) -> None: ...

        @staticmethod
        def delete() -> None: ...  # noqa: D102

        @staticmethod
        def get(url: str | Callable) -> TrackerState | None: ...  # noqa: D102

        @staticmethod
        def get_for_update(url: str) -> TrackerState | None: ...  # noqa: D102

        @staticmethod
        def select(selector: Callable) -> TrackerState: ...  # noqa: D102

        @staticmethod
        def order_by(selector: int | Callable) -> TrackerState: ...  # noqa: D102

        @staticmethod
        def limit(limit: int) -> list[TrackerState]: ...  # noqa: D102

        def __iter__(self) -> Generator[TrackerState]: ...  # noqa: D105


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
        torrents = orm.Set("TorrentState", reverse="trackers")
        failures = orm.Optional(int, size=32, default=0)

        def __init__(self, *args: Any, **kwargs) -> None:  # noqa: ANN401
            # Sanitize and canonicalize the tracker URL
            sanitized = get_uniformed_tracker_url(kwargs["url"])
            if sanitized:
                kwargs["url"] = sanitized
            else:
                msg = f"Could not canonicalize tracker URL ({kwargs['url']})"
                raise MalformedTrackerURLException(msg)

            super().__init__(*args, **kwargs)

    return TrackerState
