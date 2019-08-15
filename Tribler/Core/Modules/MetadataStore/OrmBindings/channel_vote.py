from __future__ import absolute_import

from datetime import datetime

from pony import orm


def define_binding(db):
    class ChannelVote(db.Entity):
        """
        This ORM class represents votes cast for a channel. A single instance (row), represents a vote from a single
        peer (public key) for a single channel (ChannelMetadata entry, essentially represented by a public_key+id_
        pair). To allow only a single vote from the channel, it keeps track of when the vote was cast (vote_date)
        and what amount was used locally to bump it (last_amount).
        """

        rowid = orm.PrimaryKey(int, size=64, auto=True)
        voter = orm.Required("ChannelPeer")
        channel = orm.Required("ChannelMetadata", reverse='individual_votes')
        orm.composite_key(voter, channel)
        last_amount = orm.Optional(float, default=0.0)
        vote_date = orm.Optional(datetime, default=datetime.utcnow)

    return ChannelVote
