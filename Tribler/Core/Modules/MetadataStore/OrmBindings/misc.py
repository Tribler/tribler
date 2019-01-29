from pony import orm

# This binding is used to store all kinds of values, like DB version, counters, etc.

def define_binding(db):
    class MiscData(db.Entity):
        name = orm.PrimaryKey(str)
        value = orm.Optional(str)

    return MiscData
