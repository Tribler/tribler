from __future__ import annotations

from typing import TypeVar

from pony.orm.core import Entity

EntityImpl = TypeVar("EntityImpl", bound=Entity)


class Layer:

    def get_or_create(self, cls: type[EntityImpl], create_kwargs=None, **kwargs) -> EntityImpl:
        """
        Get or create a db entity.

        :param cls: The Entity's class.
        :param create_kwargs: Any necessary additional keyword arguments to create the entity.
        :param kwargs: Keyword arguments to find the entity.
        :returns: A new or existing instance.
        """
        obj = cls.get_for_update(**kwargs)
        if not obj:
            if create_kwargs:
                kwargs.update(create_kwargs)
            obj = cls(**kwargs)
        return obj
