from __future__ import absolute_import

from pony import orm


def define_binding(db):
    class MiscData(db.Entity):
        """
        This binding is used to store all kinds of values, like DB version, counters, etc.
        """

        name = orm.PrimaryKey(str)
        value = orm.Optional(str)

    return MiscData
