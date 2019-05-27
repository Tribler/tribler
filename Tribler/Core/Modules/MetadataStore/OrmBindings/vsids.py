from __future__ import absolute_import, division

import math
from datetime import datetime

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY


def define_binding(db):
    # ACHTUNG! This thing should be used as a singleton, i.e. there should be only a single row there!
    # We store it as a DB object only to make the counters persistent.

    # VSIDS-based votes ratings
    # We use VSIDS since it provides an efficient way to add temporal decay to the voting system.
    # Temporal decay is necessary for two reasons:
    # 1. We do not gossip _unsubscription_ events, but we want votes decline for channels that go out of favor
    # 2. We want to promote the fresh content
    #
    # There are two differences with the classic VSIDS:
    # a. We scale the bump amount with passage of time, instead of on each bump event.
    #    By default, the bump amount scales 2.71 per 23hrs. Note though, that we only count Tribler uptime
    #    for this purpose. This is intentional, so the ratings do not suddenly drop after the user skips a week
    #    of uptime.
    # b. Repeated votes by some peer to some channel _do not add up_. Instead, the vote is refreshed by substracting
    #    the old amount from the current vote (it is stored in the DB), and adding the new one (1.0 votes, scaled). This
    #    is the reason why we have to keep the old votes in the DB, and normalize the old votes last_amount values - to
    #    keep them in the same "normalization space" to be compatible with the current votes values.

    # This binding is used to store normalization data and stats for VSIDS
    class Vsids(db.Entity):
        rowid = orm.PrimaryKey(int)
        bump_amount = orm.Required(float)
        total_activity = orm.Required(float)
        last_bump = orm.Required(datetime)
        rescale_threshold = orm.Optional(float, default=10.0 ** 100)
        exp_period = orm.Optional(float, default=24.0 * 60 * 60)  # decay e times over this period

        @db_session
        def rescale(self, norm):
            for channel in db.ChannelMetadata.select(lambda g: g.status != LEGACY_ENTRY):
                channel.votes /= norm
            for vote in db.ChannelVote.select():
                vote.last_amount /= norm

            self.total_activity /= norm
            self.bump_amount /= norm
            db.ChannelMetadata.votes_scaling = self.bump_amount

        # Normalization routine should normally be called only in case the values in the DB do not look normal
        @db_session
        def normalize(self):
            # If we run the normalization for the first time during the runtime, we have to gather the activity from DB
            self.total_activity = self.total_activity or orm.sum(g.votes for g in db.ChannelMetadata)
            channel_count = orm.count(db.ChannelMetadata.select(lambda g: g.status != LEGACY_ENTRY))
            if not channel_count:
                return
            if self.total_activity > 0.0:
                self.rescale(self.total_activity/channel_count)
                self.bump_amount = 1.0
            db.ChannelMetadata.votes_scaling = self.bump_amount

        @db_session
        def bump_channel(self, channel, vote):
            # Substract the last vote by the same peer from the total vote amount for this channel.
            # This effectively puts a cap of 1.0 vote from a peer on a channel
            channel.votes -= vote.last_amount
            self.total_activity -= vote.last_amount

            vote.last_amount = self.bump_amount
            channel.votes += self.bump_amount

            self.total_activity += self.bump_amount
            self.bump_amount *= math.exp((datetime.utcnow() - self.last_bump).total_seconds() / self.exp_period)
            self.last_bump = datetime.utcnow()
            if self.bump_amount > self.rescale_threshold:
                self.rescale(self.bump_amount)

            db.ChannelMetadata.votes_scaling = self.bump_amount

        @classmethod
        @db_session
        def create_default_vsids(cls):
            return cls(rowid=0,
                       bump_amount=1.0,
                       total_activity=(orm.sum(g.votes for g in db.ChannelMetadata) or 0.0),
                       last_bump=datetime.utcnow())
    return Vsids
