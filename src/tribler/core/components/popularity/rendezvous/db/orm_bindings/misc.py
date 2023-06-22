from pony.orm import Optional, PrimaryKey


def define_binding(db):
    class MiscData(db.Entity):
        name = PrimaryKey(str)
        value = Optional(str)

    return MiscData
