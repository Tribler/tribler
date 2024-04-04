from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator, Set

from tribler.core.torrent_checker.dataclasses import HealthInfo

if TYPE_CHECKING:
    from typing_extensions import Self


class DBResult(list):
    """
    Mock a Pony ORM result.
    """

    def order_by(self, _: int) -> DBResult:
        """
        Order by last check time.
        """
        if len(self) > 0:
            if isinstance(self[0], MockTrackerState):
                self.sort(key=lambda x: x.last_check)
            elif isinstance(self[0], MockTorrentState):
                self.sort(key=lambda x: x.seeders, reverse=True)
        return self

    def limit(self, limit: int) -> DBResult:
        """
        Limit the results to a given limit.
        """
        while len(self) > limit:
            self.pop(-1)
        return self


class MockEntity:
    """
    A mocked Pony ORM Entity.
    """

    instances: list

    def __call__(self: Self, *args, **kwargs) -> Self:  # noqa: ANN002
        """
        Create a new MockEntity.
        """
        return self.__class__(*args, **kwargs)

    def __iter__(self: Self) -> Iterator[Self]:
        """
        Create an iterable from our known instances.
        """
        return iter(self.__class__.instances)

    def select(self: Self, selector: Callable[[Self], bool]) -> DBResult:
        """
        Apply a selector to our known instances.
        """
        return DBResult(instance for instance in self.__class__.instances if selector(instance))

    def get(self: Self, selector: Callable[[Self], bool] | None = None, **kwargs) -> Self | None:
        """
        Get the instance belonging to the selector.
        """
        for instance in self.instances:
            if selector is not None:
                if selector(instance):
                    return instance
            elif all(getattr(instance, key) == kwargs[key] for key in kwargs):
                return instance
        return None

    def get_for_update(self: Self, **kwargs) -> Self | None:
        """
        Get the instane belonging to the given keyword arguments.
        """
        for instance in self.__class__.instances:
            if all(getattr(instance, key, None) == kwargs[key] for key in kwargs):
                return instance
        return None

    def set(self: Self, **kwargs) -> None:
        """
        Set the given attributes to the given values.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    def delete(self: Self) -> None:
        """
        Delete this instance.
        """
        self.__class__.instances.remove(self)


class MockTrackerState(MockEntity):
    """
    A mocked TrackerState Pony ORM database object.
    """

    instances = []

    def __init__(self, url: str = "", last_check: int = 0, alive: bool = True, torrents: Set | None = None,
                 failures: int = 0) -> None:
        """
        Create a new MockTrackerState and add it to our known instances.
        """
        self.__class__.instances.append(self)

        self.rowid = 0
        self.url = url
        self.last_check = last_check
        self.alive = alive
        self.torrents = torrents or set()
        self.failures = failures


class MockTorrentState(MockEntity):
    """
    A mocked TorrentState Pony ORM database object.
    """

    instances = []

    def __init__(self, infohash: bytes = b"", seeders: int = 0, leechers: int = 0, last_check: int = 0,  # noqa: PLR0913
                 self_checked: bool = False, has_data: bool = True, metadata: Set | None = None,
                 trackers: Set | None = None) -> None:
        """
        Create a new MockTrackerState and add it to our known instances.
        """
        self.__class__.instances.append(self)

        self.rowid = 0
        self.infohash = infohash
        self.seeders = seeders
        self.leechers = leechers
        self.last_check = last_check
        self.self_checked = self_checked
        self.has_data = has_data
        self.metadata = metadata or set()
        self.trackers = trackers or set()

    @classmethod
    def from_health(cls: type[Self], health: HealthInfo) -> Self:
        """
        Create from health info.
        """
        return cls(infohash=health.infohash, seeders=health.seeders, leechers=health.leechers,
                   last_check=health.last_check, self_checked=health.self_checked)

    def to_health(self) -> HealthInfo:
        """
        Cast to health info.
        """
        return HealthInfo(self.infohash, self.seeders, self.leechers, self.last_check, self.self_checked)
