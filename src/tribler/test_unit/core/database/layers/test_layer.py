from __future__ import annotations

from typing import TYPE_CHECKING

from ipv8.test.base import TestBase

from tribler.core.database.layers.layer import Layer

if TYPE_CHECKING:
    from typing_extensions import Self


class MockEntity:
    """
    A mocked-up database entity.
    """

    def __init__(self, /, **kwargs) -> None:
        """
        Create a new MockEntity and store the kwargs.
        """
        self.init_kwargs = kwargs

    @classmethod
    def get_for_update(cls: type[Self], /, **kwargs) -> type[Self] | None:
        """
        Mimic fetching the entity from the database.
        """
        return cls(**kwargs)


class MockUnknownEntity(MockEntity):
    """
    A mocked-up database entity that cannot be retrieved.
    """

    @classmethod
    def get_for_update(cls: type[Self], /, **kwargs) -> type[Self] | None:
        """
        Mimic fetching the entity from the database.
        """
        del kwargs
        return None


class TestLayer(TestBase):
    """
    Tests for the Layer base class.
    """

    def test_retrieve_existing(self) -> None:
        """
        Test retrieving a known entity.
        """
        layer = Layer()

        value = layer.get_or_create(MockEntity)

        self.assertIsNotNone(value)
        self.assertEqual(value.init_kwargs, {})

    def test_create_no_kwargs_no_create(self) -> None:
        """
        Test creating a new entity without kwargs or create kwargs.
        """
        layer = Layer()

        value = layer.get_or_create(MockUnknownEntity)

        self.assertIsNotNone(value)
        self.assertEqual(value.init_kwargs, {})

    def test_create_no_kwargs_with_create(self) -> None:
        """
        Test creating a new entity without kwargs but with create kwargs.
        """
        layer = Layer()

        value = layer.get_or_create(MockUnknownEntity, create_kwargs={"a": 1})

        self.assertIsNotNone(value)
        self.assertEqual(value.init_kwargs, {"a": 1})

    def test_create_with_kwargs_no_create(self) -> None:
        """
        Test creating a new entity with kwargs but without create kwargs.
        """
        layer = Layer()

        value = layer.get_or_create(MockUnknownEntity, a=1)

        self.assertIsNotNone(value)
        self.assertEqual(value.init_kwargs, {"a": 1})

    def test_create_with_kwargs_with_create(self) -> None:
        """
        Test creating a new entity with both kwargs and create kwargs.
        """
        layer = Layer()

        value = layer.get_or_create(MockUnknownEntity, create_kwargs={"a": 1}, b=2)

        self.assertIsNotNone(value)
        self.assertEqual(value.init_kwargs, {"a": 1, "b": 2})
