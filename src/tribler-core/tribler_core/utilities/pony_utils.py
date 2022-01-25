from typing import Type

from pony.orm.core import Entity


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
