from typing import Type

from pony.orm.core import Entity, select


# pylint: disable=bad-staticmethod-argument
def get_or_create(cls: Type[Entity], create_kwargs=None, **kwargs) -> Entity:
    """Get or create db entity.
    Args:
        cls: Entity's class, eg: `self.instance.Peer`
        create_kwargs: Additional arguments for creating new entity
        **kwargs: Arguments for selecting or for creating in case of missing entity

    Returns: Entity's instance
    """
    obj = cls.get_for_update(**kwargs)
    if not obj:
        if create_kwargs:
            kwargs.update(create_kwargs)
        obj = cls(**kwargs)
    return obj


def get_max(cls: Type[Entity], column_name='rowid') -> int:
    """Get max row ID of an db.Entity.
    Args:
        cls: Entity's class, eg: `self.instance.Peer`
        column_name: Name of the column to aggregate
    Returns: Max row ID or 0.
    """
    return select(max(getattr(obj, column_name)) for obj in cls).get() or 0
