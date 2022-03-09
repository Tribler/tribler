from datetime import datetime

from pony import orm


def define_binding(db):
    class ChannelPeer(db.Entity):
        """
        This binding stores public keys of IPv8 peers that sent us some GigaChannel data. It is used by the
        voting system.
        """

        rowid = orm.PrimaryKey(int, size=64, auto=True)
        public_key = orm.Required(bytes, unique=True)
        individual_votes = orm.Set("ChannelVote", reverse='voter')
        added_on = orm.Optional(datetime, default=datetime.utcnow)

    return ChannelPeer
