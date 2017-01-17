import json
import logging
from binascii import hexlify
from random import sample
from struct import pack
from time import time
from traceback import print_stack

from twisted.python.threadable import isInIOThread

from Tribler.community.basecommunity import BaseCommunity
from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.Core.simpledefs import NTFY_CHANNEL, NTFY_TORRENT
from Tribler.Core.simpledefs import NTFY_DISCOVERED
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.exception import MetaNotFoundException
from Tribler.dispersy.message import (DropMessage, DelayMessageByProof, DropPacket, Packet,
                                      DelayPacketByMissingMessage, DelayPacketByMissingMember)
from Tribler.dispersy.resolution import LinearResolution, PublicResolution, DynamicResolution
from Tribler.dispersy.util import call_on_reactor_thread
from .message import DelayMessageReqChannelMessage
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics
logger = logging.getLogger(__name__)

# TODO REMOVE BACKWARD COMPATIBILITY: Delete this import
from Tribler.community.channel.compatibility import ChannelCompatibility, ChannelConversion


METADATA_TYPES = [u'name', u'description', u'swift-url', u'swift-thumbnails', u'video-info', u'metadata-json']


def warnIfNotDispersyThread(func):
    def invoke_func(*args, **kwargs):
        if not isInIOThread():
            logger.critical("This method MUST be called on the DispersyThread")
            print_stack()
            return None
        else:
            return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


class ChannelCommunity(BaseCommunity):

    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """

    def __init__(self, *args, **kwargs):
        super(ChannelCommunity, self).__init__(*args, **kwargs)

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete the following 2 assignments
        self.compatibility = ChannelCompatibility(self)
        self.compatibility_mode = True

        self._channel_id = None
        self._channel_name = None
        self._channel_description = None

        self.tribler_session = None
        self.integrate_with_tribler = None

        self._peer_db = None
        self._channelcast_db = None

    def initialize(self, tribler_session=None):
        self.tribler_session = tribler_session
        self.integrate_with_tribler = tribler_session is not None

        super(ChannelCommunity, self).initialize()

        if self.integrate_with_tribler:
            from Tribler.Core.simpledefs import NTFY_PEERS, NTFY_CHANNELCAST

            # tribler channelcast database
            self._peer_db = tribler_session.open_dbhandler(NTFY_PEERS)
            self._channelcast_db = tribler_session.open_dbhandler(NTFY_CHANNELCAST)

            # tribler channel_id
            result = self._channelcast_db._db.fetchone(
                u"SELECT id, name, description FROM Channels WHERE dispersy_cid = ? and (peer_id <> -1 or peer_id ISNULL)",
                (buffer(self._master_member.mid),
                 ))
            if result is not None:
                self._channel_id, self._channel_name, self._channel_description = result

        else:
            try:
                message = self._get_latest_channel_message()
                if message:
                    self._channel_id = self.cid
            except (MetaNotFoundException, RuntimeError):
                pass

            from Tribler.community.allchannel.community import AllChannelCommunity
            for community in self.dispersy.get_communities():
                if isinstance(community, AllChannelCommunity):
                    self._channelcast_db = community._channelcast_db

    def initiate_meta_messages(self):
        batch_delay = 3.0

        # 30/11/11 Boudewijn: we frequently see dropped packets when joining a channel.  this can be
        # caused when a sync results in both torrent and modification messages.  when the
        # modification messages are processed first they will all cause the associated torrent
        # message to be requested, when these are received they are duplicates.  solution: ensure
        # that the modification messages are processed after messages that they can request.  normal
        # priority is 128, therefore, modification_priority is one less
        modification_priority = 128 - 1

        self.register_traversal("Channel",
                                MemberAuthentication(),
                                LinearResolution(),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=130),
                                CommunityDestination(node_count=10))
        self.register_traversal("Torrent",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=129),
                                CommunityDestination(node_count=10))
        self.register_traversal("Playlist",
                                MemberAuthentication(),
                                LinearResolution(),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))
        self.register_traversal("Comment",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))
        self.register_traversal("Modification",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=modification_priority),
                                CommunityDestination(node_count=10))
        self.register_traversal("PlaylistTorrent",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))
        self.register_traversal("Moderation",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))
        self.register_traversal("MarkTorrent",
                                MemberAuthentication(),
                                DynamicResolution(LinearResolution(), PublicResolution()),
                                FullSyncDistribution(enable_sequence_number=False,
                                                     synchronization_direction=u"DESC",
                                                     priority=128),
                                CommunityDestination(node_count=10))
        self.register_traversal("MissingChannel",
                                NoAuthentication(),
                                PublicResolution(),
                                DirectDistribution(),
                                CandidateDestination())

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete deprecated call
        return (super(ChannelCommunity, self).initiate_meta_messages() +
                self.compatibility.deprecated_meta_messages())

    def initiate_conversions(self):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        return [DefaultConversion(self), ChannelConversion(self)]

    def on_basemsg(self, messages):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method

        # Apparently the big switch is happening,
        # start talking newspeak:
        self.compatibility_mode = False
        super(ChannelCommunity, self).on_basemsg(messages)

    @property
    def dispersy_sync_response_limit(self):
        return 25 * 1024

    CHANNEL_CLOSED, CHANNEL_SEMI_OPEN, CHANNEL_OPEN, CHANNEL_MODERATOR = range(4)
    CHANNEL_ALLOWED_MESSAGES = ([],
                                [u"comment", u"mark_torrent"],
                                [u"torrent",
                                 u"comment",
                                 u"modification",
                                 u"playlist_torrent",
                                 u"moderation",
                                 u"mark_torrent"],
                                [u"channel",
                                 u"torrent",
                                 u"playlist",
                                 u"comment",
                                 u"modification",
                                 u"playlist_torrent",
                                 u"moderation",
                                 u"mark_torrent"])

    def get_channel_id(self):
        return self._channel_id

    def get_channel_name(self):
        return self._channel_name

    def get_channel_description(self):
        return self._channel_description

    def get_channel_mode(self):
        public = set()
        permitted = set()

        for meta in self.get_meta_messages():
            if isinstance(meta.resolution, DynamicResolution):
                policy, _ = self._timeline.get_resolution_policy(meta, self.global_time + 1)
            else:
                policy = meta.resolution

            if isinstance(policy, PublicResolution):
                public.add(meta.name)
            else:
                allowed, _ = self._timeline.allowed(meta)
                if allowed:
                    permitted.add(meta.name)

        def isCommunityType(state, checkPermitted=False):
            for type in ChannelCommunity.CHANNEL_ALLOWED_MESSAGES[state]:
                if type not in public:
                    if not (checkPermitted and type in permitted):
                        return False
            return True

        isModerator = isCommunityType(ChannelCommunity.CHANNEL_MODERATOR, True)
        if isCommunityType(ChannelCommunity.CHANNEL_OPEN):
            return ChannelCommunity.CHANNEL_OPEN, isModerator

        if isCommunityType(ChannelCommunity.CHANNEL_SEMI_OPEN):
            return ChannelCommunity.CHANNEL_SEMI_OPEN, isModerator

        return ChannelCommunity.CHANNEL_CLOSED, isModerator

    def set_channel_mode(self, mode):
        curmode, isModerator = self.get_channel_mode()
        if isModerator and mode != curmode:
            public_messages = ChannelCommunity.CHANNEL_ALLOWED_MESSAGES[mode]

            new_policies = []
            for meta in self.get_meta_messages():
                if isinstance(meta.resolution, DynamicResolution):
                    if meta.name in public_messages:
                        new_policies.append((meta, meta.resolution.policies[1]))
                    else:
                        new_policies.append((meta, meta.resolution.policies[0]))

            self.create_dynamic_settings(new_policies)

    def create_channel(self, name, description, store=True, update=True, forward=True):
        self._disp_create_channel(name, description, store, update, forward)

    @call_on_reactor_thread
    def _disp_create_channel(self, name, description, store=True, update=True, forward=True):
        name = unicode(name[:255])
        description = unicode(description[:1023])

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"channel")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.claim_global_time(),),
                                payload=(name, description))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            options = self.get_traversal("Channel",
                                         auth=(self._my_member,),
                                         dist=(self.claim_global_time(),))
            self.store_update_forward(options, "Channel", store, update, forward, name, description)

    def check_channel(self, header, message):
        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)

        yield header

    def on_channel(self, header, message):
        if self.integrate_with_tribler:
            assert self._cid == self._master_member.mid
            logger.debug("%s %s", header.candidate, self._cid.encode("HEX"))

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            self._channel_id = self._channelcast_db.on_channel_from_dispersy(self._master_member.mid,
                                                                             peer_id,
                                                                             message.name,
                                                                             message.description)

            self.tribler_session.notifier.notify(NTFY_CHANNEL, NTFY_DISCOVERED, None,
                                                 {"name": message.name,
                                                  "description": message.description,
                                                  "dispersy_cid": self._cid.encode("hex")})

            # emit signal of channel creation if the channel is created by us
            if authentication_member == self._my_member:
                self._channel_name = message.name
                self._channel_description = message.description

                from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_CREATED
                channel_data = {u'channel': self,
                                u'name': message.name,
                                u'description': message.description}
                self.tribler_session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_CREATED, None, channel_data)
        else:
            self._channel_id = self._master_member.mid
            authentication_member = header.authentication.member

            self._channelcast_db.setChannelId(self._channel_id, authentication_member == self._my_member)

    def _disp_create_torrent_from_torrentdef(self, torrentdef, timestamp, store=True, update=True, forward=True):
        files = torrentdef.get_files_as_unicode_with_length()
        self._disp_create_torrent(torrentdef.get_infohash(), timestamp,
                                  torrentdef.get_name_as_unicode(), tuple(files),
                                  torrentdef.get_trackers_as_single_tuple(), store, update, forward)

    def _disp_create_torrent(self, infohash, timestamp, name, files, trackers, store=True, update=True, forward=True):
        global_time = self.claim_global_time()
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"torrent")

            current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)
            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(global_time,),
                                payload=(infohash, timestamp, name, files, trackers))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            current_policy = self.message_traversals["Torrent"].res_type.default

            # files is a tuple of tuples (actually a list in tuple form)
            max_len = self.dispersy_sync_bloom_filter_bits / 8
            base_len = 20 + 8 + len(name) # infohash, timestamp, name
            tracker_len = sum([len(tracker) for tracker in trackers])
            file_len = sum([len(f[0]) + 8 for f in files]) # file name, length
            # Check if the message fits in the bloomfilter
            if (base_len + tracker_len + file_len > max_len) and (len(trackers) > 10):
                # only use first 10 trackers, .torrents in the wild have been seen to have 1000+ trackers...
                trackers = trackers[:10]
                tracker_len = sum([len(tracker) for tracker in trackers])
            if base_len + tracker_len + file_len > max_len:
                # reduce files by the amount we are currently to big
                reduce_by = max_len / (base_len + tracker_len + file_len * 1.0)
                nr_files_to_include = int(len(files) * reduce_by)
                files = sample(files, nr_files_to_include)
            # trackers is a tuple of trackers (instead of a list)
            options = self.get_traversal("Torrent",
                                         auth=(self._my_member,),
                                         res=(current_policy.implement(),),
                                         dist=(global_time,))
            self.store_update_forward(options, "channel.Torrent", store, update, forward,
                                      infohash,
                                      timestamp,
                                      name,
                                      list(files),
                                      list(trackers))

    def _disp_create_torrents(self, torrentlist, store=True, update=True, forward=True):
        for infohash, timestamp, name, files, trackers in torrentlist:
            self._disp_create_torrent(infohash, timestamp, name, files, trackers, store, update, forward)

    def check_torrent(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)
        yield header

    def on_torrent(self, header, message):
        if self.integrate_with_tribler:
            torrentlist = []
            dispersy_id = header.packet_id
            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            # sha_other_peer = (sha1(str(message.candidate.sock_addr) + self.my_member.mid))
            torrentlist.append(
                (self._channel_id,
                 dispersy_id,
                 peer_id,
                 message.infohash,
                 message.timestamp,
                 message.name,
                 [(f.path, f.len) for f in message.files],
                 message.trackers))
            self._logger.debug("torrent received: %s on channel: %s", message.infohash, self._master_member)

            self.tribler_session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None,
                                                 {"infohash": hexlify(message.infohash),
                                                  "timestamp": message.timestamp,
                                                  "name": message.name,
                                                  "files": [(f.path, f.len) for f in message.files],
                                                  "trackers": message.trackers,
                                                  "dispersy_cid": self._cid.encode("hex")})
            if header.candidate and header.candidate.sock_addr:
                _barter_statistics.dict_inc_bartercast(
                    BartercastStatisticTypes.TORRENTS_RECEIVED,
                    # sha_other_peer)
                    "%s:%s" % (header.candidate.sock_addr[0], header.candidate.sock_addr[1]))
            self._channelcast_db.on_torrents_from_dispersy(torrentlist)
        else:
            self._channelcast_db.newTorrent(header)
            self._logger.debug("torrent received: %s on channel: %s", message.infohash, self._master_member)
            if header.candidate and header.candidate.sock_addr:
                _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TORRENTS_RECEIVED,
                                                       "%s:%s" % (header.candidate.sock_addr[0],
                                                                  header.candidate.sock_addr[1]))

    def undo_torrent(self, header, message, redo=False):
        dispersy_id = header.packet_id
        self._channelcast_db.on_remove_torrent_from_dispersy(self._channel_id, dispersy_id, redo)

    def remove_torrents(self, dispersy_ids):
        for dispersy_id in dispersy_ids:
            message = self._dispersy.load_message_by_packetid(self, dispersy_id)
            if message:
                if not message.undone:
                    self.create_undo(message)

                else:  # hmm signal gui that this message has been removed already
                    self.undo_torrent(message, None)

    def remove_playlists(self, dispersy_ids):
        for dispersy_id in dispersy_ids:
            message = self._dispersy.load_message_by_packetid(self, dispersy_id)
            if message:
                if not message.undone:
                    self.create_undo(message)

                else:  # hmm signal gui that this message has been removed already
                    self.undo_playlist(message, None)

    # create, check or receive playlists
    @call_on_reactor_thread
    def create_playlist(self, name, description, infohashes=[], store=True, update=True, forward=True):
        self._disp_create_playlist(name, description)
        meta = self.get_meta_message(u"playlist") if self.compatibility_mode else self.get_meta_message(u"basemsg")
        message = self._dispersy.get_last_message(self, self._my_member, meta)
        if len(infohashes) > 0:
            self._disp_create_playlist_torrents(message, infohashes, store, update, forward)

    @call_on_reactor_thread
    def _disp_create_playlist(self, name, description, store=True, update=True, forward=True):
        name = unicode(name[:255])
        description = unicode(description[:1023])

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"playlist")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.claim_global_time(),),
                                payload=(name, description))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            options = self.get_traversal("Playlist",
                                         auth=(self._my_member,),
                                         dist=(self.claim_global_time(),))
            self.store_update_forward(options, "Playlist", store, update, forward, name, description)

    def check_playlist(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)
        yield header

    def on_playlist(self, header, message):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            self._channelcast_db.on_playlist_from_dispersy(self._channel_id,
                                                           dispersy_id,
                                                           peer_id,
                                                           unicode(message.name),
                                                           unicode(message.description))

    def undo_playlist(self, header, message, redo=False):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            self._channelcast_db.on_remove_playlist_from_dispersy(self._channel_id, dispersy_id, redo)

    # create, check or receive comments
    @call_on_reactor_thread
    def create_comment(self, text, timestamp, reply_to, reply_after, playlist_id, infohash, store=True, update=True,
                       forward=True):
        reply_to_message = reply_to
        reply_after_message = reply_after
        playlist_message = playlist_id

        if reply_to:
            reply_to_message = self._dispersy.load_message_by_packetid(self, reply_to)
        if reply_after:
            reply_after_message = self._dispersy.load_message_by_packetid(self, reply_after)
        if playlist_id:
            playlist_message = self._get_message_from_playlist_id(playlist_id)
        self._disp_create_comment(text, timestamp, reply_to_message,
                                   reply_after_message, playlist_message,
                                   infohash, store, update, forward)

    @call_on_reactor_thread
    def _disp_create_comment(self, text, timestamp, reply_to_message, reply_after_message, playlist_message, infohash,
                             store=True, update=True, forward=True):
        reply_to_mid = None
        reply_to_global_time = None
        if reply_to_message:
            message = reply_to_message.load_message()
            reply_to_mid = message.authentication.member.mid
            reply_to_global_time = message.distribution.global_time

        reply_after_mid = None
        reply_after_global_time = None
        if reply_after_message:
            message = reply_after_message.load_message()
            reply_after_mid = message.authentication.member.mid
            reply_after_global_time = message.distribution.global_time

        text = unicode(text[:1023])
        global_time = self.claim_global_time()
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"comment")
            current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)
            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(global_time,), payload=(text,
                                                                      timestamp, reply_to_mid, reply_to_global_time,
                                                                      reply_after_mid, reply_after_global_time,
                                                                      playlist_message, infohash))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            current_policy = self.message_traversals["Comment"].res_type.default

            options = self.get_traversal("Comment",
                                         auth=(self._my_member,),
                                         res=(current_policy.implement(),),
                                         dist=(global_time,))
            self.store_update_forward(options, "Comment", store, update, forward, text,
                                      timestamp, playlist_message.packet_id, infohash, reply_to_mid, reply_to_global_time,
                                      reply_after_mid, reply_after_global_time, playlist_message.authentication.member.mid,
                                      playlist_message.distribution.global_time)

    def check_comment(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)
        yield header

    def on_comment(self, header, message):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            mid_global_time = pack('!20sQ', header.authentication.member.mid, header.distribution.global_time)

            reply_to_id = None
            if message.replytomid:
                try:
                    reply_to_id = self._get_packet_id(
                        message.replytoglobaltime,
                        message.replytomid)
                except:
                    reply_to_id = pack('!20sQ', message.replytomid, message.replytoglobaltime)

            reply_after_id = None
            if message.replyaftermid:
                try:
                    reply_after_id = self._get_packet_id(
                        message.replyafterglobaltime,
                        message.replyaftermid)
                except:
                    reply_after_id = pack(
                        '!20sQ',
                        message.replyaftermid,
                        message.replyafterglobaltime)

            playlist_dispersy_id = None
            if message.playlistpacket:
                playlist_dispersy_id = message.playlistpacket

            self._channelcast_db.on_comment_from_dispersy(self._channel_id,
                                                          dispersy_id,
                                                          mid_global_time,
                                                          peer_id,
                                                          message.text,
                                                          message.timestamp,
                                                          reply_to_id,
                                                          reply_after_id,
                                                          playlist_dispersy_id,
                                                          message.infohash)

    def undo_comment(self, header, message, redo=False):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id

            infohash = message.infohash
            self._channelcast_db.on_remove_comment_from_dispersy(self._channel_id, dispersy_id, infohash, redo)

    def remove_comment(self, dispersy_id):
        message = self._dispersy.load_message_by_packetid(self, dispersy_id)
        if message:
            self.create_undo(message)

    # modify channel, playlist or torrent
    @call_on_reactor_thread
    def modifyChannel(self, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            latest_modifications[type] = self._get_latest_modification_from_channel_id(type)
        modification_on_message = self._get_latest_channel_message()

        for type, value in modifications.iteritems():
            type = unicode(type)
            timestamp = long(time())
            self._disp_create_modification(type, value, timestamp,
                                           modification_on_message,
                                           latest_modifications[type], store,
                                           update, forward)

    @call_on_reactor_thread
    def modifyPlaylist(self, playlist_id, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            latest_modifications[type] = self._get_latest_modification_from_playlist_id(playlist_id, type)

        modification_on_message = self._get_message_from_playlist_id(playlist_id)
        for type, value in modifications.iteritems():
            type = unicode(type)
            timestamp = long(time())
            self._disp_create_modification(type, value, timestamp,
                                           modification_on_message,
                                           latest_modifications[type], store,
                                           update, forward)

    @call_on_reactor_thread
    def modifyTorrent(self, channeltorrent_id, modifications, store=True, update=True, forward=True):
        latest_modifications = {}
        for type, value in modifications.iteritems():
            type = unicode(type)
            try:
                latest_modifications[type] = self._get_latest_modification_from_torrent_id(channeltorrent_id, type)
            except:
                logger.error(exc_info=True)

        modification_on_message = self._get_message_from_torrent_id(channeltorrent_id)
        for type, value in modifications.iteritems():
            timestamp = long(time())
            self._disp_create_modification(type, value, timestamp,
                                           modification_on_message,
                                           latest_modifications[type], store,
                                           update, forward)

    def _disp_create_modification(self, modification_type, modification_value, timestamp, modification_on,
                                  latest_modification, store=True, update=True, forward=True):
        modification_type = unicode(modification_type)
        modification_value = unicode(modification_value[:1023])

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            latest_modification_mid = None
            latest_modification_global_time = None
            if latest_modification:
                message = latest_modification.load_message()
                latest_modification_mid = message.authentication.member.mid
                latest_modification_global_time = message.distribution.global_time

            meta = self.get_meta_message(u"modification")
            global_time = self.claim_global_time()
            current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)
            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(global_time,),
                                payload=(modification_type, modification_value,
                                         timestamp, modification_on, latest_modification,
                                         latest_modification_mid,
                                         latest_modification_global_time))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            global_time = self.claim_global_time()
            current_policy = self.message_traversals["Modification"].res_type.default
            options = self.get_traversal("Modification",
                                         auth=(self._my_member,),
                                         res=(current_policy.implement(),),
                                         dist=(global_time,))

            if latest_modification:
                message = latest_modification.load_message()
                self.store_update_forward(options, "Modification", store, update, forward,
                                          modification_type, modification_value,
                                          timestamp, modification_on.authentication.member.mid,
                                          modification_on.distribution.global_time,
                                          message.authentication.member.mid,
                                          message.distribution.global_time)
            else:
                self.store_update_forward(options, "Modification", store, update, forward,
                                          modification_type, modification_value,
                                          timestamp, modification_on.authentication.member.mid,
                                          modification_on.distribution.global_time)

    def _get_message(self, global_time, mid):
        assert isinstance(global_time, (int, long))
        assert isinstance(mid, str)
        assert len(mid) == 20
        if global_time and mid:
            try:
                packet_id, packet, message_name = self.dispersy.database.execute(
                    u""" SELECT sync.id, sync.packet, meta_message.name
                    FROM sync
                    JOIN member ON (member.id = sync.member)
                    JOIN meta_message ON (meta_message.id = sync.meta_message)
                    WHERE sync.community = ? AND sync.global_time = ? AND member.mid = ?""",
                    (self.database_id, global_time, buffer(mid))).next()
            except StopIteration:
                raise DropPacket("Missing message")

            return packet_id, str(packet), message_name

    def _get_modification_on(self, header, message):
        modification_on = None
        try:
            packet_id, packet, message_name = self._get_message(message.globaltime, message.mid)
            modification_on = Packet(self.get_meta_message(message_name), packet, packet_id)
        except DropPacket:
            member = self.get_member(mid=message.mid)
            if not member:
                raise DelayPacketByMissingMember(self, message.mid)
            raise DelayPacketByMissingMessage(self, member, message.globaltime)
        return modification_on.load_message()

    def check_modification(self, header, message):
        th_handler = self.tribler_session.lm.rtorrent_handler

        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)

        modification_on = self._get_modification_on(header, message)

        # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Torrent" and u"metadata-json"
        if (((hasattr(modification_on.payload, 'unserialized')
              and modification_on.payload.unserialized[0][0] == "Torrent")
             or (hasattr(modification_on, 'name') and modification_on.name == u"torrent"))
                and message.modificationtype == u"metadata-json"):
            try:
                data = json.loads(message.modificationvalue)
                thumbnail_hash = data[u'thumb_hash'].decode('hex')
            except ValueError:
                yield DropMessage(header, "Not compatible json format")
            else:
                modifying_dispersy_id = modification_on.packet_id
                torrent_id = self._channelcast_db._db.fetchone(
                    u"SELECT torrent_id FROM _ChannelTorrents WHERE dispersy_id = ?",
                    (modifying_dispersy_id,))
                infohash = self._channelcast_db._db.fetchone(
                    u"SELECT infohash FROM Torrent WHERE torrent_id = ?", (torrent_id,))
                if infohash:
                    infohash = str2bin(infohash)
                    logger.debug(
                        "Incoming metadata-json with infohash %s from %s",
                        infohash.encode("HEX"),
                        header.candidate.sock_addr[0])

                    if not th_handler.has_metadata(thumbnail_hash):
                        @call_on_reactor_thread
                        def callback(_, message=header):
                            self.on_messages([header])
                        logger.debug(
                            "Will try to download metadata-json thumbnail with infohash %s from %s",
                            infohash.encode("HEX"),
                            header.candidate.sock_addr[0])
                        th_handler.download_metadata(header.candidate, thumbnail_hash, usercallback=callback,
                                                     timeout=CANDIDATE_WALK_LIFETIME)
                        return
        yield header

    def _get_prev_modification_packet(self, header, message):
        try:
            packet_id, packet, message_name = self._get_message(message.prevglobaltime, message.prevmid)
            return Packet(self._community.get_meta_message(message_name), packet, packet_id)
        except:
            return None

    def on_modification(self, header, message):
        if self.integrate_with_tribler:
            channeltorrentDict = {}
            playlistDict = {}

            modification_on = self._get_modification_on(header, message)

            dispersy_id = header.packet_id
            message_name = modification_on.name
            mid_global_time = "%s@%d" % (header.authentication.member.mid, header.distribution.global_time)

            modifying_dispersy_id = modification_on.packet_id
            modification_type = unicode(message.modificationtype)
            modification_value = message.modificationvalue
            timestamp = message.timestamp

            prev_modification_packet = self._get_prev_modification_packet(header, message)
            if prev_modification_packet:
                prev_modification_id = prev_modification_packet.packet_id
            else:
                prev_modification_id = message.prevmid
            prev_modification_global_time = message.prevglobaltime

            # load local ids from database
            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Torrent"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Torrent")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"torrent")):
                channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)
                if not channeltorrent_id:
                    self._logger.info("CANNOT FIND channeltorrent_id %s", modifying_dispersy_id)
                channeltorrentDict[modifying_dispersy_id] = channeltorrent_id
                # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Playlist"
            elif ((hasattr(modification_on.payload, 'unserialized')
                   and modification_on.payload.unserialized[0][0] == "Playlist")
                  or (hasattr(modification_on, 'name') and modification_on.name == u"playlist")):
                playlist_id = self._get_playlist_id_from_message(modifying_dispersy_id)
                playlistDict[modifying_dispersy_id] = playlist_id

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            # always store metadata
            self._channelcast_db.on_metadata_from_dispersy(message_name,
                                                           channeltorrentDict.get(modifying_dispersy_id, None),
                                                           playlistDict.get(modifying_dispersy_id, None),
                                                           self._channel_id,
                                                           dispersy_id,
                                                           peer_id,
                                                           mid_global_time,
                                                           modification_type,
                                                           modification_value,
                                                           timestamp,
                                                           prev_modification_id,
                                                           prev_modification_global_time)

            # see if this is new information, if so call on_X_from_dispersy to update local 'cached' information
            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Torrent"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Torrent")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"torrent")):
                channeltorrent_id = channeltorrentDict[modifying_dispersy_id]

                if channeltorrent_id:
                    latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type)
                    if not latest or latest.packet_id == dispersy_id:
                        self._channelcast_db.on_torrent_modification_from_dispersy(
                            channeltorrent_id, modification_type, modification_value)

            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Playlist"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Playlist")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"playlist")):
                playlist_id = playlistDict[modifying_dispersy_id]

                latest = self._get_latest_modification_from_playlist_id(playlist_id, modification_type)
                if not latest or latest.packet_id == dispersy_id:
                    self._channelcast_db.on_playlist_modification_from_dispersy(
                        playlist_id, modification_type, modification_value)

            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Channel"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Channel")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"channel")):
                latest = self._get_latest_modification_from_channel_id(modification_type)
                if not latest or latest.packet_id == dispersy_id:
                    self._channelcast_db.on_channel_modification_from_dispersy(
                        self._channel_id, modification_type, modification_value)

    def undo_modification(self, header, message, redo=False):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id

            modification_on = self._get_modification_on(header, message)
            message_name = message.name
            modifying_dispersy_id = modification_on.packet_id
            modification_type = unicode(message.modificationtype)

            # load local ids from database
            playlist_id = channeltorrent_id = None
            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Torrent"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Torrent")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"torrent")):
                channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)

                # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Playlist"
            elif ((hasattr(modification_on.payload, 'unserialized')
                   and modification_on.payload.unserialized[0][0] == "Playlist")
                  or (hasattr(modification_on, 'name') and modification_on.name == u"playlist")):
                playlist_id = self._get_playlist_id_from_message(modifying_dispersy_id)
            self._channelcast_db.on_remove_metadata_from_dispersy(self._channel_id, dispersy_id, redo)

            # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Torrent"
            if ((hasattr(modification_on.payload, 'unserialized')
                 and modification_on.payload.unserialized[0][0] == "Torrent")
                    or (hasattr(modification_on, 'name') and modification_on.name == u"torrent")):
                latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type)

                if not latest or latest.packet_id == dispersy_id:
                    # TODO REMOVE BACKWARD COMPATIBILITY: Keep only inner-if positive body
                    if hasattr(latest.payload, 'unserialized'):
                        modification_value = latest.payload.unserialized[0][1].modificationvalue if latest else ''
                        self._channelcast_db.on_torrent_modification_from_dispersy(
                            channeltorrent_id, modification_type, modification_value)
                    else:
                        modification_value = latest.payload.modification_value if latest else ''
                        self._channelcast_db.on_torrent_modification_from_dispersy(
                            channeltorrent_id, modification_type, modification_value)

                # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Playlist"
            elif ((hasattr(modification_on.payload, 'unserialized')
                   and modification_on.payload.unserialized[0][0] == "Playlist")
                  or (hasattr(modification_on, 'name') and modification_on.name == u"playlist")):
                latest = self._get_latest_modification_from_playlist_id(playlist_id, modification_type)

                if not latest or latest.packet_id == dispersy_id:
                    # TODO REMOVE BACKWARD COMPATIBILITY: Keep only inner-if positive body
                    if hasattr(latest.payload, 'unserialized'):
                        modification_value = latest.payload.unserialized[0][1].modificationvalue if latest else ''
                        self._channelcast_db.on_playlist_modification_from_dispersy(
                            playlist_id, modification_type, modification_value)
                    else:
                        modification_value = latest.payload.modification_value if latest else ''
                        self._channelcast_db.on_playlist_modification_from_dispersy(
                            playlist_id, modification_type, modification_value)

                # TODO REMOVE BACKWARD COMPATIBILITY: Only check for "Channel"
            elif ((hasattr(modification_on.payload, 'unserialized')
                   and modification_on.payload.unserialized[0][0] == "Channel")
                  or (hasattr(modification_on, 'name') and modification_on.name == u"channel")):
                latest = self._get_latest_modification_from_channel_id(modification_type)

                if not latest or latest.packet_id == dispersy_id:
                    # TODO REMOVE BACKWARD COMPATIBILITY: Keep only inner-if positive body
                    if hasattr(latest.payload, 'unserialized'):
                        modification_value = latest.payload.unserialized[0][1].modificationvalue if latest else ''
                        self._channelcast_db.on_channel_modification_from_dispersy(
                            self._channel_id, modification_type, modification_value)
                    else:
                        modification_value = latest.payload.modification_value if latest else ''
                        self._channelcast_db.on_channel_modification_from_dispersy(
                            self._channel_id, modification_type, modification_value)

    # create, check or receive playlist_torrent messages
    @call_on_reactor_thread
    def create_playlist_torrents(self, playlist_id, infohashes, store=True, update=True, forward=True):
        playlist_packet = self._get_message_from_playlist_id(playlist_id)
        self._disp_create_playlist_torrents(playlist_packet, infohashes, store, update, forward)

    def remove_playlist_torrents(self, playlist_id, dispersy_ids):
        for dispersy_id in dispersy_ids:
            message = self._dispersy.load_message_by_packetid(self, dispersy_id)
            if message:
                if not message.undone:
                    self.create_undo(message)
                else:
                    self._disp_undo_playlist_torrent([(None, None, message)])

    @call_on_reactor_thread
    def _disp_create_playlist_torrents(self, playlist_packet, infohashes, store=True, update=True, forward=True):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"playlist_torrent")
            current_policy, _ = self._timeline.get_resolution_policy(meta, self.global_time + 1)

            messages = []
            for infohash in infohashes:
                message = meta.impl(authentication=(self._my_member,),
                                    resolution=(current_policy.implement(),),
                                    distribution=(self.claim_global_time(),),
                                    payload=(infohash, playlist_packet))
                messages.append(message)

            self._dispersy.store_update_forward(messages, store, update, forward)
        else:
            current_policy = self.message_traversals["PlaylistTorrent"].res_type.default

            options = self.get_traversal("PlaylistTorrent",
                                         auth=(self._my_member,),
                                         dist=(self.claim_global_time(),),
                                         res=(current_policy.implement(),))
            for infohash in infohashes:
                self.store_update_forward(options, "PlaylistTorrent", store, update, forward,
                                          infohash,
                                          playlist_packet.authentication.member.mid,
                                          playlist_packet.distribution.global_time)

    def check_playlisttorrent(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        try:
            self._get_playlist(header, message)
        except DelayPacketByMissingMessage, e:
            yield e

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)
        yield header

    def _get_playlist(self, header, message):
        try:
            packet_id, packet, message_name = self._get_message(message.globaltime, message.mid)
        except DropPacket:
            member = self.dispersy.get_member(mid=message.mid)
            if not member:
                raise DelayPacketByMissingMember(self, message.mid)
            raise DelayPacketByMissingMessage(self, member, message.globaltime)

        return Packet(self.get_meta_message(message_name), packet, packet_id)

    def on_playlisttorrent(self, header, message):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            playlist_dispersy_id = self._get_playlist(header, message).packet_id

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            self._channelcast_db.on_playlist_torrent(dispersy_id,
                                                     playlist_dispersy_id,
                                                     peer_id,
                                                     message.infohash)

    def undo_playlisttorrent(self, header, message, redo=False):
        if self.integrate_with_tribler:
            playlist_dispersy_id = self._get_playlist(header, message).packet_id

            self._channelcast_db.on_remove_playlist_torrent(self._channel_id,
                                                            playlist_dispersy_id,
                                                            message.infohash,
                                                            redo)

    # check or receive moderation messages
    @call_on_reactor_thread
    def _disp_create_moderation(self, text, timestamp, severity, cause, store=True, update=True, forward=True):
        causemessage = self._dispersy.load_message_by_packetid(self, cause)
        causemessage = causemessage.load_message()
        if causemessage:
            text = unicode(text[:1023])
            global_time = self.claim_global_time()

            # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
            if self.compatibility_mode:
                meta = self.get_meta_message(u"moderation")
                current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)

                message = meta.impl(authentication=(self._my_member,),
                                    resolution=(current_policy.implement(),),
                                    distribution=(global_time,),
                                    payload=(text, timestamp, severity, causemessage))
                self._dispersy.store_update_forward([message], store, update, forward)
            else:
                current_policy = self.message_traversals["Moderation"].res_type.default

                options = self.get_traversal("Moderation", auth=(self._my_member,),
                                             dist=(global_time,),
                                             res=(current_policy.implement(),))
                self.store_update_forward(options, "Moderation", store, update, forward,
                                          text,
                                          timestamp,
                                          severity,
                                          causemessage.authentication.member.mid,
                                          causemessage.distribution.global_time)

    def check_moderation(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)

        yield header

    def _get_cause_packet(self, header, message):
        try:
            packet_id, packet, message_name = self._get_message(message.causeglobaltime, message.causemid)
            return Packet(self.get_meta_message(message_name), packet, packet_id)

        except DropPacket:
            member = self.get_member(mid=message.causemid)
            if not member:
                raise DelayPacketByMissingMember(self, message.causemid)
            raise DelayPacketByMissingMessage(self, member, message.causeglobaltime)

    def on_moderation(self, header, message):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            # if cause packet is present, it is enforced by conversion
            causepacket = self._get_cause_packet(header, message)
            cause = causepacket.packet_id
            cause_message = causepacket.load_message()
            authentication_member = cause_message.authentication.member
            if authentication_member == self._my_member:
                by_peer_id = None
            else:
                by_peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

            # determine if we are reverting latest
            updateTorrent = False

            # TODO REMOVE BACKWARD COMPATIBILITY: Only keep payload.unserialized[0][1], refactor into modification_type
            cause_payload = cause_message.payload.unserialized[0][1] \
                            if hasattr(cause_message.payload, 'unserialized') else cause_message.payload
            # TODO REMOVE BACKWARD COMPATIBILITY: Only keep _get_modificition_on
            modification_on = self._get_modification_on(cause_message, cause_message.payload.unserialized[0][1]) \
                              if hasattr(cause_message.payload, 'unserialized') \
                              else cause_message.payload.modification_on
            modifying_dispersy_id = modification_on.packet_id
            channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)
            if channeltorrent_id:
                modification_type = unicode(cause_payload.modificationtype)

                latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type)
                if not latest or latest.packet_id == cause_message.packet_id:
                    updateTorrent = True

            self._channelcast_db.on_moderation(self._channel_id,
                                               dispersy_id, peer_id,
                                               by_peer_id, cause,
                                               message.text,
                                               message.timestamp,
                                               message.severity)

            if updateTorrent:
                latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type)
                # TODO REMOVE BACKWARD COMPATIBILITY: Only keep payload.unserialized[0][1],
                # refactor into modification_value
                latest_payload = latest.payload.unserialized[0][1] if hasattr(cause_message.payload, 'unserialized') \
                                                                   else latest.payload
                modification_value = latest_payload.modificationvalue if latest else ''
                self._channelcast_db.on_torrent_modification_from_dispersy(
                    channeltorrent_id, modification_type, modification_value)

    def undo_moderation(self, header, message, redo=False):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            self._channelcast_db.on_remove_moderation(self._channel_id, dispersy_id, redo)

    # check or receive torrent_mark messages
    @call_on_reactor_thread
    def _disp_create_mark_torrent(self, infohash, type, timestamp, store=True, update=True, forward=True):
        global_time = self.claim_global_time()
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"mark_torrent")
            current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)

            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(global_time,),
                                payload=(infohash, type, timestamp))
            self._dispersy.store_update_forward([message], store, update, forward)
        else:
            current_policy = self.message_traversals["MarkTorrent"].res_type.default

            options = self.get_traversal("MarkTorrent",
                                         auth=(self._my_member,),
                                         dist=(global_time,),
                                         res=(current_policy.implement(),))
            self.store_update_forward(options, "MarkTorrent", store, update, forward, infohash, type, timestamp)

    def check_marktorrent(self, header, message):
        if not self._channel_id:
            yield DelayMessageReqChannelMessage(header)

        accepted, proof = self._timeline.check(header)
        if not accepted:
            yield DelayMessageByProof(header)
        yield header

    def on_marktorrent(self, header, message):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            global_time = header.distribution.global_time

            authentication_member = header.authentication.member
            if authentication_member == self._my_member:
                peer_id = None
            else:
                peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
            self._channelcast_db.on_mark_torrent(
                self._channel_id,
                dispersy_id,
                global_time,
                peer_id,
                message.infohash,
                message.type,
                message.timestamp)

    def undo_mark_torrent(self, header, message, redo=False):
        if self.integrate_with_tribler:
            dispersy_id = header.packet_id
            self._channelcast_db.on_remove_mark_torrent(self._channel_id, dispersy_id, redo)

    def disp_create_missing_channel(self, candidate, includeSnapshot):
        logger.debug("%s sending missing-channel %s %s", candidate, self._cid.encode("HEX"), includeSnapshot)
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self._meta_messages[u"missing-channel"]
            request = meta.impl(distribution=(self.global_time,), destination=(candidate,), payload=(includeSnapshot,))
            self._dispersy._forward([request])
        else:
            options = self.get_traversal("MissingChannel",
                                         dist=(self.global_time,),
                                         dest=(candidate,))
            self.forward(options, "MissingChannel", includeSnapshot)

    def on_missingchannel(self, header, message):
        channelmessage = self._get_latest_channel_message()
        packets = None

        if message.includeSnapshot:
            if packets is None:
                packets = []
                packets.append(channelmessage.packet)

                torrents = self._channelcast_db.getRandomTorrents(self._channel_id)
                for infohash in torrents:
                    tormessage = self._get_message_from_torrent_infohash(infohash)
                    if tormessage:
                        packets.append(tormessage.packet)

            self._dispersy._send_packets([header.candidate], packets,
                                         self, "-caused by missing-channel-response-snapshot-")

        else:
            self._dispersy._send_packets([header.candidate], [channelmessage.packet],
                                         self, "-caused by missing-channel-response-")

    def on_dynamic_settings(self, *args, **kwargs):
        Community.on_dynamic_settings(self, *args, **kwargs)
        if self._channel_id and self.integrate_with_tribler:
            self._channelcast_db.on_dynamic_settings(self._channel_id)

    # helper functions
    @warnIfNotDispersyThread
    def _get_latest_channel_message(self):
        # TODO REMOVE BACKWARD COMPATIBILITY: Assign to negative case
        channel_meta_old = self.get_meta_message(u"channel")
        channel_meta_new = self.get_meta_message(u"basemsg")
        packet = None
        packet_id = None
        statement = self._dispersy.database.execute(
            u"SELECT packet, id FROM sync WHERE meta_message = ? OR meta_message = ? ORDER BY global_time DESC",
            (channel_meta_old.database_id, channel_meta_new.database_id))

        while True:
            # 1. get the packet
            try:
                packet, packet_id = statement.next()
            except StopIteration:
                raise RuntimeError("Could not find requested packet")

            message = self._dispersy.convert_packet_to_message(str(packet))
            if message:
                # TODO REMOVE BACKWARD COMPATIBILITY: Remove all but inner-if positive body
                if hasattr(message.payload, 'unserialized'):
                    if message.payload.unserialized[0][0] != "Channel":
                        continue
                elif hasattr(message, 'name'):
                    assert message.name == u"channel", "Expecting a 'channel' message"
                message.packet_id = packet_id
            else:
                raise RuntimeError("Unable to convert packet, could not find channel-message for channel %d" %
                                   channel_meta.database_id)
            return message

    def _get_message_from_playlist_id(self, playlist_id):
        assert isinstance(playlist_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_id, _ = self._channelcast_db.getPlaylist(playlist_id, ('Playlists.dispersy_id',))

        # 2. get the message
        if dispersy_id and dispersy_id > 0:
            return self._dispersy.load_message_by_packetid(self, dispersy_id)

    def _get_playlist_id_from_message(self, dispersy_id):
        assert isinstance(dispersy_id, (int, long))
        return self._channelcast_db._db.fetchone(u"SELECT id FROM _Playlists WHERE dispersy_id = ?", (dispersy_id,))

    def _get_message_from_torrent_id(self, torrent_id):
        assert isinstance(torrent_id, (int, long))

        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db.getTorrentFromChannelTorrentId(torrent_id, ['ChannelTorrents.dispersy_id'])

        # 2. get the message
        if dispersy_id and dispersy_id > 0:
            return self._dispersy.load_message_by_packetid(self, dispersy_id)

    def _get_message_from_torrent_infohash(self, torrent_infohash):
        assert isinstance(torrent_infohash, str), 'infohash is a %s' % type(torrent_infohash)
        assert len(torrent_infohash) == 20, 'infohash has length %d' % len(torrent_infohash)

        # 1. get the dispersy identifier from the channel_id
        dispersy_id = self._channelcast_db.getTorrentFromChannelId(self._channel_id,
                                                                   torrent_infohash,
                                                                   ['ChannelTorrents.dispersy_id'])

        if dispersy_id and dispersy_id > 0:
            # 2. get the message
            return self._dispersy.load_message_by_packetid(self, dispersy_id)

    def _get_torrent_id_from_message(self, dispersy_id):
        assert isinstance(dispersy_id, (int, long)), "dispersy_id type is '%s'" % type(dispersy_id)

        return self._channelcast_db._db.fetchone(u"SELECT id FROM _ChannelTorrents WHERE dispersy_id = ?", (dispersy_id,))

    def _get_latest_modification_from_channel_id(self, type_name):
        assert isinstance(type_name, basestring), "type_name is not a basestring: %s" % repr(type_name)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(
            u"SELECT dispersy_id, prev_global_time " + \
            u"FROM ChannelMetaData WHERE type = ? " + \
            u"AND channel_id = ? " + \
            u"AND id NOT IN (SELECT metadata_id FROM MetaDataTorrent) " + \
            u"AND id NOT IN (SELECT metadata_id FROM MetaDataPlaylist) " + \
            u"AND dispersy_id not in (SELECT cause FROM Moderations " + \
            u"WHERE channel_id = ?) ORDER BY prev_global_time DESC",
            (type_name, self._channel_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    def _get_latest_modification_from_torrent_id(self, channeltorrent_id, type_name):
        assert isinstance(channeltorrent_id, (int, long)), "channeltorrent_id type is '%s'" % type(channeltorrent_id)
        assert isinstance(type_name, basestring), "type_name is not a basestring: %s" % repr(type_name)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time " + \
                                                         u"FROM ChannelMetaData, MetaDataTorrent " + \
                                                         u"WHERE ChannelMetaData.id = MetaDataTorrent.metadata_id " + \
                                                         u"AND type = ? AND channeltorrent_id = ? " + \
                                                         u"AND dispersy_id not in " + \
                                                         u"(SELECT cause FROM Moderations WHERE channel_id = ?) " + \
                                                         u"ORDER BY prev_global_time DESC",
            (type_name, channeltorrent_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    def _get_latest_modification_from_playlist_id(self, playlist_id, type_name):
        assert isinstance(playlist_id, (int, long)), "playlist_id type is '%s'" % type(playlist_id)
        assert isinstance(type_name, basestring), "type_name is not a basestring: %s" % repr(type_name)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time " + \
                                                         u"FROM ChannelMetaData, MetaDataPlaylist " + \
                                                         u"WHERE ChannelMetaData.id = MetaDataPlaylist.metadata_id " + \
                                                         u"AND type = ? AND playlist_id = ? " + \
                                                         u"AND dispersy_id not in " + \
                                                         u"(SELECT cause FROM Moderations WHERE channel_id = ?) " + \
                                                         u"ORDER BY prev_global_time DESC",
            (type_name, playlist_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    @warnIfNotDispersyThread
    def _determine_latest_modification(self, list):

        if len(list) > 0:
            # 1. determine if we have a conflict
            max_global_time = list[0][1]
            conflicting_messages = []
            for dispersy_id, prev_global_time in list:
                if prev_global_time >= max_global_time:
                    try:
                        message = self._dispersy.load_message_by_packetid(self, dispersy_id)
                        if message:
                            message = message.load_message()
                            conflicting_messages.append(message)

                            max_global_time = prev_global_time
                    except RuntimeError:
                        pass
                else:
                    break

            # 2. see if we have a conflict
            if len(conflicting_messages) > 1:

                # 3. solve conflict using mid to sort on
                def cleverSort(message_a, message_b):
                    public_key_a = message_a.authentication.member.public_key
                    public_key_b = message_a.authentication.member.public_key

                    if public_key_a == public_key_b:
                        return cmp(message_b.distribution.global_time, message_a.distribution.global_time)

                    return cmp(public_key_a, public_key_b)

                conflicting_messages.sort(cleverSort)

            if len(conflicting_messages) > 0:
                # 4. return first message
                return conflicting_messages[0]

    @warnIfNotDispersyThread
    def _get_packet_id(self, global_time, mid):
        if global_time and mid:
            try:
                packet_id, = self._dispersy.database.execute(u"""
                    SELECT sync.id
                    FROM sync
                    JOIN member ON (member.id = sync.member)
                    JOIN meta_message ON (meta_message.id = sync.meta_message)
                    WHERE sync.community = ? AND sync.global_time = ? AND member.mid = ?""",
                                                             (self.database_id, global_time, buffer(mid))).next()
            except StopIteration:
                pass
            return packet_id
