from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from ipv8.test.base import TestBase

from tribler.core.database.layers.health import HealthDataAccessLayer, ResourceType
from tribler.core.torrent_checker.dataclasses import HealthInfo, Source

if TYPE_CHECKING:
    from typing_extensions import Self


class MockResource:
    """
    A mocked Resource that stored is call kwargs.
    """

    def __init__(self, **kwargs) -> None:
        """
        Create a MockResouce and store its kwargs.
        """
        self.get_kwargs = kwargs

    @classmethod
    def get(cls: type[Self], **kwargs) -> type[Self]:
        """
        Fake a search using the given kwargs and return an instance of ourselves.
        """
        return cls(**kwargs)

    @classmethod
    def get_for_update(cls: type[Self], /, **kwargs) -> type[Self] | None:
        """
        Mimic fetching the resource from the database.
        """
        del kwargs
        return None



class MockEntity(MockResource, SimpleNamespace):
    """
    Allow a db binding to write whatever they want to this class.
    """

    CREATED = []

    def __init__(self, **kwargs) -> None:
        """
        Create a new MockEntity and add it to the CREATED list.
        """
        super().__init__(**kwargs)
        self.CREATED.append(self)


class MockDatabase:
    """
    Mock the bindings that others will inherit from.
    """

    Entity = MockEntity
    Resource = MockResource


class MockKnowledgeDataAccessLayer:
    """
    A mocked KnowledgeDataAccessLayer.
    """

    def __init__(self) -> None:
        """
        Create a new mocked KnowledgeDataAccessLayer.
        """
        self.instance = MockDatabase()
        self.Resource = self.instance.Resource
        self.instance.Entity.CREATED = []


class TestHealthDataAccessLayer(TestBase):
    """
    Tests for the HealthDataAccessLayer.
    """

    def test_get_torrent_health(self) -> None:
        """
        Test if torrents with the correct infohash are retrieved for their health info.
        """
        hdal = HealthDataAccessLayer(MockKnowledgeDataAccessLayer())

        health = hdal.get_torrent_health("01" * 20)

        self.assertEqual("01" * 20, health.get_kwargs["torrent"].get_kwargs["name"])
        self.assertEqual(ResourceType.TORRENT, health.get_kwargs["torrent"].get_kwargs["type"])

    def test_add_torrent_health(self) -> None:
        """
        Test if adding torrent health leads to the correct database calls.
        """
        hdal = HealthDataAccessLayer(MockKnowledgeDataAccessLayer())
        hdal.TorrentHealth = MockEntity

        hdal.add_torrent_health(HealthInfo(b"\x01" * 20, 7, 42, 1337))
        added, = hdal.TorrentHealth.CREATED

        self.assertEqual(b"01" * 20, added.get_kwargs["torrent"].get_kwargs["name"])
        self.assertEqual(ResourceType.TORRENT, added.get_kwargs["torrent"].get_kwargs["type"])
        self.assertEqual(7, added.seeders)
        self.assertEqual(42, added.leechers)
        self.assertEqual(Source.UNKNOWN, added.source)
