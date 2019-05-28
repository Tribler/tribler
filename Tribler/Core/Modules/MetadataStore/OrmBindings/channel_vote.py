from __future__ import absolute_import

from datetime import datetime

from pony import orm


def define_binding(db):
    class ChannelVote(db.Entity):
        rowid = orm.PrimaryKey(int, size=64, auto=True)
        voter = orm.Required("ChannelPeer")
        channel = orm.Required("ChannelMetadata", reverse='individual_votes')
        orm.composite_key(voter, channel)
        last_amount = orm.Optional(float, default=0.0)
        vote_date = orm.Optional(datetime, default=datetime.utcnow)

    return ChannelVote
