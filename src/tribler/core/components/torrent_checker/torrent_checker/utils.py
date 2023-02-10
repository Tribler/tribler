from __future__ import annotations

from asyncio import gather
from typing import Awaitable, Dict, Iterable, List, TypeVar, Union, cast

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import InfohashHealth, TrackerResponse


T = TypeVar("T")


async def gather_coros(coros: Iterable[Awaitable[T]]) -> List[Union[T, BaseException]]:
    """
    A replacement of asyncio.gather() with a proper typing support for coroutines with the same result type
    """
    results = await gather(*coros, return_exceptions=True)
    return cast(List[Union[T, BaseException]], results)


def filter_non_exceptions(items: List[Union[T, BaseException]]) -> List[T]:
    """
    Removes exceptions from the result of the `await gather_coro(...)` call
    """
    return [item for item in items if not isinstance(item, BaseException)]


def aggregate_responses_for_infohash(infohash: bytes, responses: List[TrackerResponse]) -> InfohashHealth:
    """
    Finds the "best" health info (with the max number of seeders) for a specified infohash
    """
    result = InfohashHealth(infohash, last_check=0)
    for response in responses:
        for health in response.torrent_health_list:
            if health.infohash == infohash and health.seeders > result.seeders:
                result = health
    return result


def aggregate_health_by_infohash(health_list: List[InfohashHealth]) -> List[InfohashHealth]:
    """
    For each infohash in the health list, finds the "best" health info (with the max number of seeders)
    """
    d: Dict[bytes, InfohashHealth] = {}
    for health in health_list:
        infohash = health.infohash
        if infohash not in d or health.seeders > d[infohash].seeders:
            d[infohash] = health
    return list(d.values())
