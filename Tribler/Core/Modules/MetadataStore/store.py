from __future__ import absolute_import, division

import logging
import math
import os
from binascii import hexlify
from datetime import datetime, timedelta
from time import sleep

from ipv8.database import database_blob

import lz4.frame

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings import (
    channel_metadata, channel_node, channel_peer, channel_vote, misc, torrent_metadata, torrent_state, tracker_state)
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_metadata import BLOB_EXTENSION
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import LEGACY_ENTRY
from Tribler.Core.Modules.MetadataStore.serialization import (
    CHANNEL_TORRENT, DELETED, REGULAR_TORRENT, read_payload_with_offset, time2int)
from Tribler.Core.exceptions import InvalidSignatureException

BETA_DB_VERSIONS = [0, 1]
CURRENT_DB_VERSION = 2

CLOCK_STATE_FILE = "clock.state"

NO_ACTION = 0
UNKNOWN_CHANNEL = 1
UPDATED_OUR_VERSION = 2
GOT_NEWER_VERSION = 4
UNKNOWN_TORRENT = 5
DELETED_METADATA = 6

# This table should never be used from ORM directly.
# It is created as a VIRTUAL table by raw SQL and
# maintained by SQL triggers.
sql_create_fts_table = """
    CREATE VIRTUAL TABLE IF NOT EXISTS FtsIndex USING FTS5
        (title, content='ChannelNode', prefix = '2 3 4 5',
         tokenize='porter unicode61 remove_diacritics 1');"""

sql_add_fts_trigger_insert = """
    CREATE TRIGGER IF NOT EXISTS fts_ai AFTER INSERT ON ChannelNode
    BEGIN
        INSERT INTO FtsIndex(rowid, title) VALUES (new.rowid, new.title);
    END;"""

sql_add_fts_trigger_delete = """
    CREATE TRIGGER IF NOT EXISTS fts_ad AFTER DELETE ON ChannelNode
    BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
    END;"""

sql_add_fts_trigger_update = """
    CREATE TRIGGER IF NOT EXISTS fts_au AFTER UPDATE ON ChannelNode BEGIN
        DELETE FROM FtsIndex WHERE rowid = old.rowid;
        INSERT INTO FtsIndex(rowid, title) VALUES (new.rowid, new.title);
    END;"""

sql_add_signature_index = "CREATE INDEX SignatureIndex ON ChannelNode(signature);"
sql_add_public_key_index = "CREATE INDEX PublicKeyIndex ON ChannelNode(public_key);"
sql_add_infohash_index = "CREATE INDEX InfohashIndex ON ChannelNode(infohash);"


class BadChunkException(Exception):
    pass


class DiscreteClock(object):
    # Lamport-clock-like persistent counter
    # Horribly inefficient and stupid, but works
    store_value_name = "discrete_clock"

    def __init__(self, datastore=None):
        # This is a stupid workaround for people who reinstall Tribler
        # and lose their database. We don't know what was their channel
        # clock before, but at least we can assume that they were not
        # adding to it 1000 torrents per second constantly...
        self.clock = time2int(datetime.utcnow()) * 1000
        self.datastore = datastore

    def init_clock(self):
        if self.datastore:
            with db_session:
                store_object = self.datastore.get_for_update(name=self.store_value_name, )
                if not store_object:
                    self.datastore(name=self.store_value_name, value=str(self.clock))
                else:
                    self.clock = int(store_object.value)

    def tick(self):
        self.clock += 1
        if self.datastore:
            with db_session:
                self.datastore[self.store_value_name].value = str(self.clock)
        return self.clock


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
class Vsids(object):
    def __init__(self, mds_channel, mds_vote, mds_peer):
        self.ChannelMetadata = mds_channel
        self.ChannelVote = mds_vote
        self.ChannelPeer = mds_peer

        self.rescale_threshold = 10.0 ** 100
        self.exp_period = 24.0 * 60 * 60  # decay e times over this period
        self.total_activity = 0.0

        self.bump_amount = 1.0
        self.last_bump = datetime.utcnow()

    @db_session
    def rescale(self, norm):
        for channel in self.ChannelMetadata.select(lambda g: g.status != LEGACY_ENTRY):
            channel.votes /= norm
        for vote in self.ChannelVote.select():
            vote.last_amount /= norm

        self.total_activity /= norm
        self.bump_amount /= norm

    @db_session
    def normalize(self):
        # If we run the normalization for the first time during the runtime, we have to gather the activity from DB
        self.total_activity = self.total_activity or orm.sum(g.votes for g in self.ChannelMetadata)
        channel_count = orm.count(self.ChannelMetadata.select(lambda g: g.status != LEGACY_ENTRY))
        if not channel_count:
            return
        if self.total_activity > 0.0:
            self.rescale(self.total_activity/channel_count)
            self.bump_amount = 1.0

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


class MetadataStore(object):
    def __init__(self, db_filename, channels_dir, my_key, disable_sync=False):
        self.db_filename = db_filename
        self.channels_dir = channels_dir
        self.my_key = my_key
        self._logger = logging.getLogger(self.__class__.__name__)

        self._shutting_down = False
        self.batch_size = 10  # reasonable number, a little bit more than typically fits in a single UDP packet
        self.reference_timedelta = timedelta(milliseconds=100)
        self.sleep_on_external_thread = 0.05  # sleep this amount of seconds between batches executed on external thread

        create_db = (db_filename == ":memory:" or not os.path.isfile(self.db_filename))

        # We have to dynamically define/init ORM-managed entities here to be able to support
        # multiple sessions in Tribler. ORM-managed classes are bound to the database instance
        # at definition.
        self._db = orm.Database()

        # Possibly disable disk sync.
        # !!! ACHTUNG !!! This should be used only for special cases (e.g. DB upgrades), because
        # losing power during a write will corrupt the database.
        if disable_sync:

            # This attribute is internally called by Pony on startup, though pylint cannot detect it
            # with the static analysis.
            # pylint: disable=unused-variable
            @self._db.on_connect(provider='sqlite')
            def sqlite_disable_sync(_, connection):
                cursor = connection.cursor()
                cursor.execute("PRAGMA synchronous = 0")
            # pylint: enable=unused-variable

        self.MiscData = misc.define_binding(self._db)

        self.TrackerState = tracker_state.define_binding(self._db)
        self.TorrentState = torrent_state.define_binding(self._db)

        self.clock = DiscreteClock(None if db_filename == ":memory:" else self.MiscData)

        self.ChannelNode = channel_node.define_binding(self._db, logger=self._logger, key=my_key, clock=self.clock)
        self.TorrentMetadata = torrent_metadata.define_binding(self._db)
        self.ChannelMetadata = channel_metadata.define_binding(self._db)
        self.ChannelVote = channel_vote.define_binding(self._db)
        self.ChannelPeer = channel_peer.define_binding(self._db)
        self.vsids = Vsids(self.ChannelMetadata, self.ChannelVote, self.ChannelPeer)

        self.ChannelMetadata._channels_dir = channels_dir

        self._db.bind(provider='sqlite', filename=db_filename, create_db=create_db)
        if create_db:
            with db_session:
                self._db.execute(sql_create_fts_table)
        self._db.generate_mapping(create_tables=create_db)  # Must be run out of session scope
        if create_db:
            with db_session:
                self._db.execute(sql_add_fts_trigger_insert)
                self._db.execute(sql_add_fts_trigger_delete)
                self._db.execute(sql_add_fts_trigger_update)
                self._db.execute(sql_add_signature_index)
                self._db.execute(sql_add_public_key_index)
                self._db.execute(sql_add_infohash_index)

        if create_db:
            with db_session:
                self.MiscData(name="db_version", value=str(CURRENT_DB_VERSION))

        self.clock.init_clock()
        self.vsids.normalize()

    @db_session
    def upsert_vote(self, channel, peer_pk):
        voter = self.ChannelPeer.get(public_key=peer_pk)
        if not voter:
            voter = self.ChannelPeer(public_key=peer_pk)
        vote = self.ChannelVote.get(voter=voter, channel=channel)
        if not vote:
            vote = self.ChannelVote(voter=voter, channel=channel)
        else:
            vote.vote_date = datetime.utcnow()
        return vote

    @db_session
    def vote_bump(self, public_key, id_, voter_pk):
        channel = self.ChannelMetadata.get_for_update(public_key=public_key, id_=id_)
        if not channel:
            return
        vote = self.upsert_vote(channel, voter_pk)

        self.vsids.bump_channel(channel, vote)

    def shutdown(self):
        self._shutting_down = True
        self._db.disconnect()

    def process_channel_dir(self, dirname, channel_id, external_thread=True):
        """
        Load all metadata blobs in a given directory.
        :param dirname: The directory containing the metadata blobs.
        :param external_thread: indicate to lower levels that this is running on a background thread
        :param channel_id: public_key of the channel.
        """
        # We use multiple separate db_sessions here to limit the memory and reactor time impact,
        # but we must check the existence of the channel every time to avoid race conditions
        with db_session:
            channel = self.ChannelMetadata.get(public_key=channel_id)
            if not channel:
                return
            self._logger.debug("Starting processing channel dir %s. Channel %s local/max version %i/%i",
                               dirname, hexlify(str(channel.public_key)), channel.local_version,
                               channel.timestamp)

        for filename in sorted(os.listdir(dirname)):
            full_filename = os.path.join(dirname, filename)

            if self._shutting_down:
                return

            blob_sequence_number = None
            if filename.endswith(BLOB_EXTENSION):
                blob_sequence_number = int(filename[:-len(BLOB_EXTENSION)])
            elif filename.endswith(BLOB_EXTENSION + '.lz4'):
                blob_sequence_number = int(filename[:-len(BLOB_EXTENSION + '.lz4')])

            if blob_sequence_number is not None:
                # Skip blobs containing data we already have and those that are
                # ahead of the channel version known to us
                # ==================|          channel data       |===
                # ===start_timestamp|---local_version----timestamp|===
                # local_version is essentially a cursor pointing into the current state of update process
                with db_session:
                    channel = self.ChannelMetadata.get(public_key=channel_id)
                    if not channel:
                        return
                    if blob_sequence_number <= channel.start_timestamp or \
                            blob_sequence_number <= channel.local_version or \
                            blob_sequence_number > channel.timestamp:
                        continue
                try:
                    self.process_mdblob_file(full_filename, external_thread)
                    # We track the local version of the channel while reading blobs
                    with db_session:
                        channel = self.ChannelMetadata.get_for_update(public_key=channel_id)
                        if channel:
                            channel.local_version = blob_sequence_number
                        else:
                            return
                except InvalidSignatureException:
                    self._logger.error("Not processing metadata located at %s: invalid signature", full_filename)

        with db_session:
            channel = self.ChannelMetadata.get(public_key=channel_id)
            if not channel:
                return
            self._logger.debug("Finished processing channel dir %s. Channel %s local/max version %i/%i",
                           dirname, hexlify(str(channel.public_key)), channel.local_version,
                               channel.timestamp)

    def process_mdblob_file(self, filepath, external_thread=False):
        """
        Process a file with metadata in a channel directory.
        :param filepath: The path to the file
        :param external_thread: indicate to the lower lever that we're running in the backround thread,
            to possibly pace down the upload process
        :return ChannelNode objects list if we can correctly load the metadata
        """
        with open(filepath, 'rb') as f:
            serialized_data = f.read()

        return (self.process_compressed_mdblob(serialized_data, external_thread) if filepath.endswith('.lz4') else
                self.process_squashed_mdblob(serialized_data, external_thread))

    def process_compressed_mdblob(self, compressed_data, external_thread=False):
        try:
            decompressed_data = lz4.frame.decompress(compressed_data)
        except RuntimeError:
            self._logger.warning("Unable to decompress mdblob")
            return []
        return self.process_squashed_mdblob(decompressed_data, external_thread)

    def process_squashed_mdblob(self, chunk_data, external_thread=False):
        """
        Process raw concatenated payloads blob. This routine breaks the database access into smaller batches.
        It uses a congestion-control like algorithm to determine the optimal batch size, targeting the
        batch processing time value of self.reference_timedelta.

        :param chunk_data: the blob itself, consists of one or more GigaChannel payloads concatenated together
        :param external_thread: if this is set to True, we add some sleep between batches to allow other threads
        to get the database lock. This is an ugly workaround for Python and Twisted asynchronous programming (locking)
        imperfections. It only makes sense to use it when this routine runs on a non-reactor thread.
        :return ChannelNode objects list if we can correctly load the metadata
        """

        offset = 0
        payload_list = []
        while offset < len(chunk_data):
            payload, offset = read_payload_with_offset(chunk_data, offset)
            payload_list.append(payload)

        result = []
        total_size = len(payload_list)
        start = 0
        while start < total_size:
            end = start + self.batch_size
            batch = payload_list[start:end]
            batch_start_time = datetime.now()

            # We separate the sessions to minimize database locking.
            with db_session:
                for payload in batch:
                    result.extend(self.process_payload(payload))
            if external_thread:
                sleep(self.sleep_on_external_thread)

            # Batch size adjustment
            batch_end_time = datetime.now() - batch_start_time
            target_coeff = (batch_end_time.total_seconds() / self.reference_timedelta.total_seconds())
            if len(batch) == self.batch_size:
                # Adjust batch size only for full batches
                if target_coeff < 0.8:
                    self.batch_size += self.batch_size
                elif target_coeff > 1.0:
                    self.batch_size = int(float(self.batch_size) / target_coeff)
                self.batch_size += 1  # we want to guarantee that at least something will go through
            self._logger.debug(("Added payload batch to DB (entries, seconds): %i %f",
                                (self.batch_size, float(batch_end_time.total_seconds()))))
            start = end
        return result

    @db_session
    def process_payload(self, payload):
        """
        This routine decides what to do with a given payload and executes the necessary actions.
        To do so, it looks into the database, compares version numbers, etc.
        It returns a list of tuples each of which contain the corresponding new/old object and the actions
        that were performed on that object.
        :param payload: payload to work on
        :return: a list of tuples of (<metadata or payload>, <action type>)
        """

        if payload.metadata_type == DELETED:
            # We only allow people to delete their own entries, thus PKs must match
            node = self.ChannelNode.get_for_update(signature=payload.delete_signature,
                                                   public_key=payload.public_key)
            if node:
                node.delete()
                return [(None, DELETED_METADATA)]

        # Check if we already got an older version of the same node that we can update, and
        # check the uniqueness constraint on public_key+infohash tuple. If the received entry
        # has the same tuple as the entry we already have, update our entry if necessary.
        # This procedure is necessary to handle the case when the original author of the payload
        # had created another entry with the same infohash earlier, deleted it, and sent
        # the different versions to two different peers.
        # There is a corner case where there already exist 2 entries in our database that match both
        # update conditions:
        # A: (pk, id1, ih1)
        # B: (pk, id2, ih2)
        # Now, when we receive the payload C1:(pk, id1, ih2) or C2:(pk, id2, ih1), we have to
        # replace _both_ entries with a single one, to honor the DB uniqueness constraints.

        if payload.metadata_type not in [CHANNEL_TORRENT, REGULAR_TORRENT]:
            return []

        # Check the payload timestamp<->id_ correctness
        if payload.timestamp < payload.id_:
            return []

        # Check if we already have this payload
        node = self.ChannelNode.get_for_update(signature=payload.signature, public_key=payload.public_key)
        if node:
            return [(node, NO_ACTION)]

        # Check for a node with the same infohash
        result = []
        node = self.TorrentMetadata.get_for_update(public_key=database_blob(payload.public_key),
                                                   infohash=database_blob(payload.infohash))
        if node:
            if node.timestamp < payload.timestamp:
                node.delete()
                result.append((None, DELETED_METADATA))
            elif node.timestamp > payload.timestamp:
                result.append((node, GOT_NEWER_VERSION))
                return result
            else:
                return result
            # Otherwise, we got the same version locally and do nothing.

        # Check for the older version of the same node
        node = self.TorrentMetadata.get_for_update(public_key=database_blob(payload.public_key), id_=payload.id_)
        if node:
            if node.timestamp < payload.timestamp:
                node.set(**payload.to_dict())
                result.append((node, UPDATED_OUR_VERSION))
            elif node.timestamp > payload.timestamp:
                result.append((node, GOT_NEWER_VERSION))
            # Otherwise, we got the same version locally and do nothing.
            # The situation when something was marked for deletion, and then we got here (i.e. we have the same
            # version) should never happen, because this version should have removed the above mentioned thing earlier
            if result:
                self._logger.warning("Broken DB state!")
            return result

        if payload.metadata_type == REGULAR_TORRENT:
            result.append((self.TorrentMetadata.from_payload(payload), UNKNOWN_TORRENT))
        elif payload.metadata_type == CHANNEL_TORRENT:
            result.append((self.ChannelMetadata.from_payload(payload), UNKNOWN_CHANNEL))
            return result

        return result

    @db_session
    def get_my_channel(self):
        return self.ChannelMetadata.get_channel_with_id(self.my_key.pub().key_to_bin()[10:])

    @db_session
    def get_num_channels(self):
        return orm.count(self.ChannelMetadata.select(lambda g: g.metadata_type == CHANNEL_TORRENT))

    @db_session
    def get_num_torrents(self):
        return orm.count(self.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))
