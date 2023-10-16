import functools
import logging
from typing import Callable, Optional

from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.utilities.pony_utils import db_session

MIGRATION_METADATA = "_tribler_db_migration"

logger = logging.getLogger('Migration (TriblerDB)')


def migration(execute_only_if_version: int, set_after_successful_execution_version: Optional[int] = None):
    """ Decorator for migration functions.
    The migration executes in the single transaction. If the migration fails, the transaction is rolled back.
    The decorator also sets the metadata attribute to the decorated function. It could be checked by
    calling the `has_migration_metadata` function.
    Args:
        execute_only_if_version: Execute the migration only if the current db version is equal to this value.
        set_after_successful_execution_version: Set the db version to this value after the migration is executed.
            If it is not specified, then `set_after_successful_execution_version = execute_only_if_version + 1`
    """

    def decorator(func):
        @functools.wraps(func)
        @db_session
        def wrapper(db: TriblerDatabase, **kwargs):
            target_version = execute_only_if_version
            if target_version != db.version:
                logger.info(
                    f"Function {func.__name__} is not executed because DB version is not equal to {target_version}. "
                    f"The current db version is {db.version}"
                )
                return None

            result = func(db, **kwargs)

            next_version = set_after_successful_execution_version
            if next_version is None:
                next_version = target_version + 1
            db.version = next_version

            return result

        setattr(wrapper, MIGRATION_METADATA, {})
        return wrapper

    return decorator


def has_migration_metadata(f: Callable):
    """ Check if the function has migration metadata."""
    return hasattr(f, MIGRATION_METADATA)
