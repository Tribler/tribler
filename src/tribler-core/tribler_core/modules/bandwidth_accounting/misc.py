from pony.orm import Optional, PrimaryKey


def define_binding(db):
    class MiscData(db.Entity):
        """
        This binding is used to store all kinds of values, like DB version, counters, etc.
        """
        name = PrimaryKey(str)
        value = Optional(str)

    return MiscData
