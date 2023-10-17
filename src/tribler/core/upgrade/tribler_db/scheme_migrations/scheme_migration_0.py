from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.upgrade.tribler_db.decorator import migration


@migration(execute_only_if_version=0)
def scheme_migration_0(db: TriblerDatabase, **kwargs):  # pylint: disable=unused-argument
    """ "This is initial migration, placed here primarily for demonstration purposes.
    It doesn't do anything except set the database version to `1`.

    For upcoming migrations, there are some guidelines:
    1. functions should contain a single parameter, `db: TriblerDatabase`,
    2. they should apply the `@migration` decorator.


    Utilizing plain SQL (as seen in the example below) is considered good practice since it helps prevent potential
    inconsistencies in DB schemes in the future (model versions preceding the current one may differ from it).
    For more information see: https://github.com/Tribler/tribler/issues/7382

    The example of a migration:

        db.execute('ALTER TABLE "TorrentState" ADD "has_data" BOOLEAN DEFAULT 0')
        db.execute('UPDATE "TorrentState" SET "has_data" = 1 WHERE last_check > 0')
    """
