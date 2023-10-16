from unittest.mock import Mock

import pytest

from tribler.core.upgrade.tribler_db.decorator import has_migration_metadata, migration


def test_migration_execute_only_if_version():
    """ Test that migration is executed only if the version of the database is equal to the specified one."""

    @migration(execute_only_if_version=1)
    def test(_: Mock):
        return True

    assert test(Mock(version=1))
    assert not test(Mock(version=2))


def test_set_after_successful_execution_version():
    """ Test that the version of the database is set to the specified one after the migration is successfully
    executed.
    """

    @migration(execute_only_if_version=1, set_after_successful_execution_version=33)
    def test(_: Mock):
        ...

    db = Mock(version=1)
    test(db)

    assert db.version == 33


def test_set_after_successful_execution_version_not_specified():
    """ Test that if the version is not specified, the version of the database will be set to
    execute_only_if_version + 1
    """

    @migration(execute_only_if_version=1)
    def test(_: Mock):
        ...

    db = Mock(version=1)
    test(db)

    assert db.version == 2


def test_set_after_successful_execution_raise_an_exception():
    """ Test that if an exception is raised during the migration, the version of the database is not changed."""

    @migration(execute_only_if_version=1, set_after_successful_execution_version=33)
    def test(_: Mock):
        raise TypeError

    db = Mock(version=1)
    with pytest.raises(TypeError):
        test(db)

    assert db.version == 1


def test_set_metadata():
    """ Test that the metadata flag is set."""

    @migration(execute_only_if_version=1)
    def simple_migration(_: Mock):
        ...

    def no_migration(_: Mock):
        ...

    assert has_migration_metadata(simple_migration)
    assert not has_migration_metadata(no_migration)
