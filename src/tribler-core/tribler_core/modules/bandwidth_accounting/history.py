from pony.orm import PrimaryKey, Required


def define_binding(bandwidth_database):
    db = bandwidth_database.database

    class BandwidthHistory(db.Entity):
        """
        This ORM class represents a mutation of ones bandwidth balance.
        We store the last 100 mutations in ones bandwidth balance.
        """

        rowid = PrimaryKey(int, auto=True)
        timestamp = Required(int, size=64)
        balance = Required(int, size=64)

    return BandwidthHistory
