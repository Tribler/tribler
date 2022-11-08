import threading
from asyncio import get_event_loop
from typing import Callable, Type

from pony.orm.core import Database, Entity, select


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


async def run_threaded(db: Database, func: Callable, *args, **kwargs):
    """Run `func` threaded and close DB connection at the end of the execution.

    Args:
        db: the DB to be closed
        func: the function to be executed threaded
        *args: args for the function call
        **kwargs: kwargs for the function call

    Returns: a result of the func call.

    You should use `run_threaded` to wrap all functions that should be executed from a separate thread and work with
    the database. The `run_threaded` function ensures that all database connections opened in worker threads are
    properly closed before the Tribler shutdown.

    The Asyncio `run_in_executor` method executes its argument in a separate worker thread. After the db_session is
    over, PonyORM caches the connection to the database to re-use it again later in the same thread. It was previously
    reported that some obscure problems could be observed during the Tribler shutdown if connections in the Tribler
    worker threads are not closed properly.
    """

    def wrapper():
        try:
            return func(*args, **kwargs)
        finally:
            # @ichorid: this is a workaround for closing threadpool connections
            # Remark: maybe subclass ThreadPoolExecutor to handle this automatically?
            is_main_thread = isinstance(threading.current_thread(), threading._MainThread)  # pylint: disable=W0212
            if not is_main_thread:
                db.disconnect()

    return await get_event_loop().run_in_executor(None, wrapper)
