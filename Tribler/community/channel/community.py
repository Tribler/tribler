import json
import logging
from struct import pack
from time import time
from traceback import print_stack

from twisted.python.threadable import isInIOThread

from Tribler.Core.CacheDB.sqlitecachedb import str2bin
from Tribler.community.channel.payload import ModerationPayload
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination, CommunityDestination
from Tribler.dispersy.distribution import FullSyncDistribution, DirectDistribution
from Tribler.dispersy.message import BatchConfiguration, Message, DropMessage, DelayMessageByProof
from Tribler.dispersy.resolution import LinearResolution, PublicResolution, DynamicResolution
from Tribler.dispersy.util import call_on_reactor_thread
from .conversion import ChannelConversion
from .message import DelayMessageReqChannelMessage
from .payload import (ChannelPayload, TorrentPayload, PlaylistPayload, CommentPayload, ModificationPayload,
                      PlaylistTorrentPayload, MissingChannelPayload, MarkTorrentPayload)
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics
logger = logging.getLogger(__name__)


def warnDispersyThread(func):
    def invoke_func(*args, **kwargs):
        if not isInIOThread():
            logger.critical("This method MUST be called on the DispersyThread")
            print_stack()
            return None
        else:
            return func(*args, **kwargs)

    invoke_func.__name__ = func.__name__
    return invoke_func


class ChannelCommunity(Community):

    """
    Each user owns zero or more ChannelCommunities that other can join and use to discuss.
    """

    def __init__(self, *args, **kwargs):
        super(ChannelCommunity, self).__init__(*args, **kwargs)

        self._channel_id = None

        self.tribler_session = None
        self.integrate_with_tribler = None

        self._peer_db = None
        self._channelcast_db = None

        self._modification_types = None

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
            self._channel_id = self._channelcast_db._db.fetchone(
                u"SELECT id FROM Channels WHERE dispersy_cid = ? and (peer_id <> -1 or peer_id ISNULL)",
                (buffer(self._master_member.mid),
                 ))

            # modification_types
            self._modification_types = self._channelcast_db.modification_types

        else:
            try:
                message = self._get_latest_channel_message()
                if message:
                    self._channel_id = self.cid
            except:
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

        return super(ChannelCommunity, self).initiate_meta_messages() + [
            Message(self, u"channel",
                    MemberAuthentication(),
                    LinearResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=130),
                    CommunityDestination(node_count=10),
                    ChannelPayload(),
                    self._disp_check_channel,
                    self._disp_on_channel),
            Message(self, u"torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=129),
                    CommunityDestination(node_count=10),
                    TorrentPayload(),
                    self._disp_check_torrent,
                    self._disp_on_torrent,
                    self._disp_undo_torrent,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"playlist",
                    MemberAuthentication(),
                    LinearResolution(),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    PlaylistPayload(),
                    self._disp_check_playlist,
                    self._disp_on_playlist,
                    self._disp_undo_playlist,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"comment",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    CommentPayload(),
                    self._disp_check_comment,
                    self._disp_on_comment,
                    self._disp_undo_comment,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"modification",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False,
                                         synchronization_direction=u"DESC",
                                         priority=modification_priority),
                    CommunityDestination(node_count=10),
                    ModificationPayload(),
                    self._disp_check_modification,
                    self._disp_on_modification,
                    self._disp_undo_modification,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"playlist_torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    PlaylistTorrentPayload(),
                    self._disp_check_playlist_torrent,
                    self._disp_on_playlist_torrent,
                    self._disp_undo_playlist_torrent,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"moderation",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    ModerationPayload(),
                    self._disp_check_moderation,
                    self._disp_on_moderation,
                    self._disp_undo_moderation,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"mark_torrent",
                    MemberAuthentication(),
                    DynamicResolution(LinearResolution(), PublicResolution()),
                    FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"DESC", priority=128),
                    CommunityDestination(node_count=10),
                    MarkTorrentPayload(),
                    self._disp_check_mark_torrent,
                    self._disp_on_mark_torrent,
                    self._disp_undo_mark_torrent,
                    batch=BatchConfiguration(max_window=batch_delay)),
            Message(self, u"missing-channel",
                    NoAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    MissingChannelPayload(),
                    self._disp_check_missing_channel,
                    self._disp_on_missing_channel),
        ]

    @property
    def dispersy_sync_response_limit(self):
        return 25 * 1024

    def initiate_conversions(self):
        return [DefaultConversion(self), ChannelConversion(self)]

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
                    if checkPermitted and type in permitted:
                        continue
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

        meta = self.get_meta_message(u"channel")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_channel(self, messages):
        for message in messages:
            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            yield message

    def _disp_on_channel(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                assert self._cid == self._master_member.mid
                logger.debug("%s %s", message.candidate, self._cid.encode("HEX"))

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                self._channel_id = self._channelcast_db.on_channel_from_dispersy(self._master_member.mid,
                                                                                 peer_id,
                                                                                 message.payload.name,
                                                                                 message.payload.description)
        else:
            for message in messages:
                self._channel_id = self._master_member.mid
                authentication_member = message.authentication.member

                self._channelcast_db.setChannelId(self._channel_id, authentication_member == self._my_member)

    def _disp_create_torrent_from_torrentdef(self, torrentdef, timestamp, store=True, update=True, forward=True):
        files = torrentdef.get_files_as_unicode_with_length()
        return (self._disp_create_torrent(torrentdef.get_infohash(), timestamp,
                                          torrentdef.get_name_as_unicode(), tuple(files),
                                          torrentdef.get_trackers_as_single_tuple(), store, update, forward))

    def _disp_create_torrent(self, infohash, timestamp, name, files, trackers, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"torrent")

        global_time = self.claim_global_time()
        current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)
        message = meta.impl(authentication=(self._my_member,),
                            resolution=(current_policy.implement(),),
                            distribution=(global_time,),
                            payload=(infohash, timestamp, name, files, trackers))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_create_torrents(self, torrentlist, store=True, update=True, forward=True):
        messages = []

        meta = self.get_meta_message(u"torrent")
        current_policy, _ = self._timeline.get_resolution_policy(meta, self.global_time + 1)
        for infohash, timestamp, name, files, trackers in torrentlist:
            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(self.claim_global_time(),),
                                payload=(infohash, timestamp, name, files, trackers))

            messages.append(message)

        self._dispersy.store_update_forward(messages, store, update, forward)
        return messages

    def _disp_check_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message

    def _disp_on_torrent(self, messages):
        if self.integrate_with_tribler:
            torrentlist = []
            for message in messages:
                dispersy_id = message.packet_id
                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                # sha_other_peer = (sha1(str(message.candidate.sock_addr) + self.my_member.mid))
                torrentlist.append(
                    (self._channel_id,
                     dispersy_id,
                     peer_id,
                     message.payload.infohash,
                     message.payload.timestamp,
                     message.payload.name,
                     message.payload.files,
                     message.payload.trackers))
                self._logger.debug("torrent received: %s on channel: %s", message.payload.infohash, self._master_member)
                if message.candidate and message.candidate.sock_addr:
                      self._logger.debug("logging torrent in bartercast statistics (%s)" % message.candidate.sock_addr)
                      _barter_statistics.dict_inc_bartercast(
                        BartercastStatisticTypes.TORRENTS_RECEIVED,
                        # sha_other_peer)
                        "%s:%s" % (message.candidate.sock_addr[0], message.candidate.sock_addr[1]))
            self._channelcast_db.on_torrents_from_dispersy(torrentlist)
        else:
            for message in messages:
                self._channelcast_db.newTorrent(message)
                self._logger.debug("torrent received: %s on channel: %s", message.payload.infohash, self._master_member)
                if message.candidate and message.candidate.sock_addr:
                    _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TORRENTS_RECEIVED,
                                                           "%s:%s" % (message.candidate.sock_addr[0], message.candidate.sock_addr[1]))

    def _disp_undo_torrent(self, descriptors, redo=False):
        for _, _, packet in descriptors:
            dispersy_id = packet.packet_id
            self._channelcast_db.on_remove_torrent_from_dispersy(self._channel_id, dispersy_id, redo)

    def remove_torrents(self, dispersy_ids):
        for dispersy_id in dispersy_ids:
            message = self._dispersy.load_message_by_packetid(self, dispersy_id)
            if message:
                if not message.undone:
                    self.create_undo(message)

                else:  # hmm signal gui that this message has been removed already
                    self._disp_undo_torrent([(None, None, message)])

    def remove_playlists(self, dispersy_ids):
        for dispersy_id in dispersy_ids:
            message = self._dispersy.load_message_by_packetid(self, dispersy_id)
            if message:
                if not message.undone:
                    self.create_undo(message)

                else:  # hmm signal gui that this message has been removed already
                    self._disp_undo_playlist([(None, None, message)])

    # create, check or receive playlists
    @call_on_reactor_thread
    def create_playlist(self, name, description, infohashes=[], store=True, update=True, forward=True):
        message = self._disp_create_playlist(name, description)
        if len(infohashes) > 0:
            self._disp_create_playlist_torrents(message, infohashes, store, update, forward)

    @call_on_reactor_thread
    def _disp_create_playlist(self, name, description, store=True, update=True, forward=True):
        name = unicode(name[:255])
        description = unicode(description[:1023])

        meta = self.get_meta_message(u"playlist")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(name, description))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_playlist(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message

    def _disp_on_playlist(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                dispersy_id = message.packet_id
                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                self._channelcast_db.on_playlist_from_dispersy(self._channel_id,
                                                               dispersy_id,
                                                               peer_id,
                                                               message.payload.name,
                                                               message.payload.description)

    def _disp_undo_playlist(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                dispersy_id = packet.packet_id
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

        meta = self.get_meta_message(u"comment")
        global_time = self.claim_global_time()
        current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)
        message = meta.impl(authentication=(self._my_member,),
                            resolution=(current_policy.implement(),),
                            distribution=(global_time,), payload=(text,
                                                                  timestamp, reply_to_mid, reply_to_global_time,
                                                                  reply_after_mid, reply_after_global_time,
                                                                  playlist_message, infohash))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_comment(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue
            yield message

    def _disp_on_comment(self, messages):
        if self.integrate_with_tribler:

            for message in messages:
                dispersy_id = message.packet_id

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                mid_global_time = pack('!20sQ', message.authentication.member.mid, message.distribution.global_time)

                reply_to_id = None
                if message.payload.reply_to_mid:
                    try:
                        reply_to_id = self._get_packet_id(
                            message.payload.reply_to_global_time,
                            message.payload.reply_to_mid)
                    except:
                        reply_to_id = pack('!20sQ', message.payload.reply_to_mid, message.payload.reply_to_global_time)

                reply_after_id = None
                if message.payload.reply_after_mid:
                    try:
                        reply_after_id = self._get_packet_id(
                            message.payload.reply_after_global_time,
                            message.payload.reply_after_mid)
                    except:
                        reply_after_id = pack(
                            '!20sQ',
                            message.payload.reply_after_mid,
                            message.payload.reply_after_global_time)

                playlist_dispersy_id = None
                if message.payload.playlist_packet:
                    playlist_dispersy_id = message.payload.playlist_packet.packet_id

                self._channelcast_db.on_comment_from_dispersy(self._channel_id,
                                                              dispersy_id,
                                                              mid_global_time,
                                                              peer_id,
                                                              message.payload.text,
                                                              message.payload.timestamp,
                                                              reply_to_id,
                                                              reply_after_id,
                                                              playlist_dispersy_id,
                                                              message.payload.infohash)

    def _disp_undo_comment(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                dispersy_id = packet.packet_id

                message = packet.load_message()
                infohash = message.payload.infohash
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
            type_id = self._modification_types[type]
            latest_modifications[type] = self._get_latest_modification_from_channel_id(type_id)
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
            type_id = self._modification_types[type]
            latest_modifications[type] = self._get_latest_modification_from_playlist_id(playlist_id, type_id)

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
            type_id = self._modification_types[type]
            try:
                latest_modifications[type] = self._get_latest_modification_from_torrent_id(channeltorrent_id, type_id)
            except:
                logger.error(exc_info=True)

        modification_on_message = self._get_message_from_torrent_id(channeltorrent_id)
        for type, value in modifications.iteritems():
            timestamp = long(time())
            self._disp_create_modification(type, value, timestamp,
                                           modification_on_message,
                                           latest_modifications[type], store,
                                           update, forward)

    def _disp_create_modification(self, modification_type, modifcation_value, timestamp, modification_on,
                                   latest_modification, store=True, update=True, forward=True):
        modification_type = unicode(modification_type)
        modifcation_value = unicode(modifcation_value[:1023])

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
                            payload=(modification_type, modifcation_value,
                                     timestamp, modification_on, latest_modification,
                                     latest_modification_mid,
                                     latest_modification_global_time))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_modification(self, messages):
        th_handler = self.tribler_session.lm.rtorrent_handler

        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            if message.payload.modification_on.name == u"torrent" and message.payload.modification_type == u"swift-thumbnails":
                try:
                    data = json.loads(message.payload.modification_value)
                    thumbnail_subpath = data[1]
                    thumbnail_hashstr = data[2]
                except:
                    yield DropMessage(message, "Not compatible json format")
                    continue
                else:
                    modifying_dispersy_id = message.payload.modification_on.packet_id
                    torrent_id = self._channelcast_db._db.fetchone(
                        u"SELECT torrent_id FROM _ChannelTorrents WHERE dispersy_id = ?",
                        (modifying_dispersy_id,))
                    infohash = self._channelcast_db._db.fetchone(
                        u"SELECT infohash FROM Torrent WHERE torrent_id = ?", (torrent_id,))
                    if infohash:
                        infohash = str2bin(infohash)
                        logger.debug(
                            "Incoming swift-thumbnails with infohash %s from %s",
                            infohash.encode("HEX"),
                            message.candidate.sock_addr[0])

                        if not th_handler.has_metadata("thumbs", infohash, thumbnail_subpath):
                            @call_on_reactor_thread
                            def callback(_, message=message):
                                self.on_messages([message])
                            logger.debug(
                                "Will try to download swift-thumbnails with infohash %s from %s",
                                infohash.encode("HEX"),
                                message.candidate.sock_addr[0])
                            th_handler.download_metadata("thumbs", message.candidate, infohash, thumbnail_subpath,
                                                         timeout=CANDIDATE_WALK_LIFETIME, usercallback=callback)
                            continue

            yield message

    def _disp_on_modification(self, messages):
        if self.integrate_with_tribler:
            channeltorrentDict = {}
            playlistDict = {}

            for message in messages:
                dispersy_id = message.packet_id
                message_name = message.payload.modification_on.name
                mid_global_time = "%s@%d" % (message.authentication.member.mid, message.distribution.global_time)

                modifying_dispersy_id = message.payload.modification_on.packet_id
                modification_type = message.payload.modification_type
                modification_type_id = self._modification_types[modification_type]
                modification_value = message.payload.modification_value
                timestamp = message.payload.timestamp

                if message.payload.prev_modification_packet:
                    prev_modification_id = message.payload.prev_modification_packet.packet_id
                else:
                    prev_modification_id = message.payload.prev_modification_id
                prev_modification_global_time = message.payload.prev_modification_global_time

                # load local ids from database
                if message_name == u"torrent":
                    channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)
                    if not channeltorrent_id:
                        self._logger.info("CANNOT FIND channeltorrent_id %s", modifying_dispersy_id)
                    channeltorrentDict[modifying_dispersy_id] = channeltorrent_id

                elif message_name == u"playlist":
                    playlist_id = self._get_playlist_id_from_message(modifying_dispersy_id)
                    playlistDict[modifying_dispersy_id] = playlist_id

                authentication_member = message.authentication.member
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
                                                               modification_type_id,
                                                               modification_value,
                                                               timestamp,
                                                               prev_modification_id,
                                                               prev_modification_global_time)

            for message in messages:
                dispersy_id = message.packet_id
                message_name = message.payload.modification_on.name

                modifying_dispersy_id = message.payload.modification_on.packet_id
                modification_type = message.payload.modification_type
                modification_type_id = self._modification_types[modification_type]
                modification_value = message.payload.modification_value

                # see if this is new information, if so call on_X_from_dispersy to update local 'cached' information
                if message_name == u"torrent":
                    channeltorrent_id = channeltorrentDict[modifying_dispersy_id]

                    if channeltorrent_id:
                        latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type_id)
                        if not latest or latest.packet_id == dispersy_id:
                            self._channelcast_db.on_torrent_modification_from_dispersy(
                                channeltorrent_id, modification_type, modification_value)

                elif message_name == u"playlist":
                    playlist_id = playlistDict[modifying_dispersy_id]

                    latest = self._get_latest_modification_from_playlist_id(playlist_id, modification_type_id)
                    if not latest or latest.packet_id == dispersy_id:
                        self._channelcast_db.on_playlist_modification_from_dispersy(
                            playlist_id, modification_type, modification_value)

                elif message_name == u"channel":
                    latest = self._get_latest_modification_from_channel_id(modification_type_id)
                    if not latest or latest.packet_id == dispersy_id:
                        self._channelcast_db.on_channel_modification_from_dispersy(
                            self._channel_id, modification_type, modification_value)

            if __debug__:
                for message in messages:
                    if message.payload.modification_on.name == u"torrent" and message.payload.modification_type == "video-info":
                        self._logger.debug("Incoming video-info with value %s", message.payload.modification_value)

    def _disp_undo_modification(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                dispersy_id = packet.packet_id

                message = packet.load_message()
                message_name = message.name
                modifying_dispersy_id = message.payload.modification_on.packet_id
                modification_type = message.payload.modification_type
                modification_type_id = self._modification_types[modification_type]

                # load local ids from database
                playlist_id = channeltorrent_id = None
                if message_name == u"torrent":
                    channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)

                elif message_name == u"playlist":
                    playlist_id = self._get_playlist_id_from_message(modifying_dispersy_id)
                self._channelcast_db.on_remove_metadata_from_dispersy(self._channel_id, dispersy_id, redo)

                if message_name == u"torrent":
                    latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type_id)

                    if not latest or latest.packet_id == dispersy_id:
                        modification_value = latest.payload.modification_value if latest else ''
                        self._channelcast_db.on_torrent_modification_from_dispersy(
                            channeltorrent_id, modification_type, modification_value)

                elif message_name == u"playlist":
                    latest = self._get_latest_modification_from_playlist_id(playlist_id, modification_type_id)

                    if not latest or latest.packet_id == dispersy_id:
                        modification_value = latest.payload.modification_value if latest else ''
                        self._channelcast_db.on_playlist_modification_from_dispersy(
                            playlist_id, modification_type, modification_value)

                elif message_name == u"channel":
                    latest = self._get_latest_modification_from_channel_id(modification_type_id)

                    if not latest or latest.packet_id == dispersy_id:
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
                self.create_undo(message)

    @call_on_reactor_thread
    def _disp_create_playlist_torrents(self, playlist_packet, infohashes, store=True, update=True, forward=True):
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
        return message

    def _disp_check_playlist_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
            yield message

    def _disp_on_playlist_torrent(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                dispersy_id = message.packet_id
                playlist_dispersy_id = message.payload.playlist.packet_id

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                self._channelcast_db.on_playlist_torrent(dispersy_id,
                                                         playlist_dispersy_id,
                                                         peer_id,
                                                         message.payload.infohash)

    def _disp_undo_playlist_torrent(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                message = packet.load_message()
                infohash = message.payload.infohash
                playlist_dispersy_id = message.payload.playlist.packet_id

                self._channelcast_db.on_remove_playlist_torrent(self._channel_id, playlist_dispersy_id, infohash, redo)

    # check or receive moderation messages
    @call_on_reactor_thread
    def _disp_create_moderation(self, text, timestamp, severity, cause, store=True, update=True, forward=True):
        causemessage = self._dispersy.load_message_by_packetid(self, cause)
        if causemessage:
            text = unicode(text[:1023])

            meta = self.get_meta_message(u"moderation")
            global_time = self.claim_global_time()
            current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)

            message = meta.impl(authentication=(self._my_member,),
                                resolution=(current_policy.implement(),),
                                distribution=(global_time,),
                                payload=(text, timestamp, severity, causemessage))
            self._dispersy.store_update_forward([message], store, update, forward)
            return message

    def _disp_check_moderation(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)

            yield message

    def _disp_on_moderation(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                dispersy_id = message.packet_id

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                # if cause packet is present, it is enforced by conversion
                cause = message.payload.causepacket.packet_id
                cause_message = message.payload.causepacket.load_message()
                authentication_member = cause_message.authentication.member
                if authentication_member == self._my_member:
                    by_peer_id = None
                else:
                    by_peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)

                # determine if we are reverting latest
                updateTorrent = False

                modifying_dispersy_id = cause_message.payload.modification_on.packet_id
                channeltorrent_id = self._get_torrent_id_from_message(modifying_dispersy_id)
                if channeltorrent_id:
                    modification_type = cause_message.payload.modification_type
                    modification_type_id = self._modification_types[modification_type]

                    latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type_id)
                    if not latest or latest.packet_id == cause_message.packet_id:
                        updateTorrent = True

                self._channelcast_db.on_moderation(self._channel_id,
                                                    dispersy_id, peer_id,
                                                    by_peer_id, cause,
                                                    message.payload.text,
                                                    message.payload.timestamp,
                                                    message.payload.severity)

                if updateTorrent:
                    latest = self._get_latest_modification_from_torrent_id(channeltorrent_id, modification_type_id)

                    modification_value = latest.payload.modification_value if latest else ''
                    self._channelcast_db.on_torrent_modification_from_dispersy(
                        channeltorrent_id, modification_type, modification_value)

    def _disp_undo_moderation(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                dispersy_id = packet.packet_id
                self._channelcast_db.on_remove_moderation(self._channel_id, dispersy_id, redo)

    # check or receive torrent_mark messages
    @call_on_reactor_thread
    def _disp_create_mark_torrent(self, infohash, type, timestamp, store=True, update=True, forward=True):
        meta = self.get_meta_message(u"mark_torrent")
        global_time = self.claim_global_time()
        current_policy, _ = self._timeline.get_resolution_policy(meta, global_time)

        message = meta.impl(authentication=(self._my_member,),
                            resolution=(current_policy.implement(),),
                            distribution=(global_time,),
                            payload=(infohash, type, timestamp))
        self._dispersy.store_update_forward([message], store, update, forward)
        return message

    def _disp_check_mark_torrent(self, messages):
        for message in messages:
            if not self._channel_id:
                yield DelayMessageReqChannelMessage(message)
                continue

            accepted, proof = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
            yield message

    def _disp_on_mark_torrent(self, messages):
        if self.integrate_with_tribler:
            for message in messages:
                dispersy_id = message.packet_id
                global_time = message.distribution.global_time

                authentication_member = message.authentication.member
                if authentication_member == self._my_member:
                    peer_id = None
                else:
                    peer_id = self._peer_db.addOrGetPeerID(authentication_member.public_key)
                self._channelcast_db.on_mark_torrent(
                    self._channel_id,
                    dispersy_id,
                    global_time,
                    peer_id,
                    message.payload.infohash,
                    message.payload.type,
                    message.payload.timestamp)

    def _disp_undo_mark_torrent(self, descriptors, redo=False):
        if self.integrate_with_tribler:
            for _, _, packet in descriptors:
                dispersy_id = packet.packet_id
                self._channelcast_db.on_remove_mark_torrent(self._channel_id, dispersy_id, redo)

    def disp_create_missing_channel(self, candidate, includeSnapshot):
        logger.debug("%s sending missing-channel %s %s", candidate, self._cid.encode("HEX"), includeSnapshot)
        meta = self._meta_messages[u"missing-channel"]
        request = meta.impl(distribution=(self.global_time,), destination=(candidate,), payload=(includeSnapshot,))
        self._dispersy._forward([request])

    # check or receive missing channel messages
    def _disp_check_missing_channel(self, messages):
        return messages

    def _disp_on_missing_channel(self, messages):
        channelmessage = self._get_latest_channel_message()
        packets = None

        for message in messages:
            if message.payload.includeSnapshot:
                if packets is None:
                    packets = []
                    packets.append(channelmessage.packet)

                    torrents = self._channelcast_db.getRandomTorrents(self._channel_id)
                    for infohash in torrents:
                        tormessage = self._get_message_from_torrent_infohash(infohash)
                        if tormessage:
                            packets.append(tormessage.packet)

                self._dispersy._send_packets([message.candidate], packets,
                                             self, "-caused by missing-channel-response-snapshot-")

            else:
                self._dispersy._send_packets([message.candidate], [channelmessage.packet],
                                             self, "-caused by missing-channel-response-")

    def on_dynamic_settings(self, *args, **kwargs):
        Community.on_dynamic_settings(self, *args, **kwargs)
        if self._channel_id and self.integrate_with_tribler:
            self._channelcast_db.on_dynamic_settings(self._channel_id)

    # helper functions
    @warnDispersyThread
    def _get_latest_channel_message(self):
        channel_meta = self.get_meta_message(u"channel")

        # 1. get the packet
        try:
            packet, packet_id = self._dispersy.database.execute(
                u"SELECT packet, id FROM sync WHERE meta_message = ? ORDER BY global_time DESC LIMIT 1",
                                                                (channel_meta.database_id,)).next()
        except StopIteration:
            raise RuntimeError("Could not find requested packet")

        message = self._dispersy.convert_packet_to_message(str(packet))
        if message:
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

    def _get_latest_modification_from_channel_id(self, type_id):
        assert isinstance(type_id, (int, long)), "type_id type is '%s'" % type(type_id)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(
            u"SELECT dispersy_id, prev_global_time " + \
            u"FROM ChannelMetaData WHERE type_id = ? " + \
            u"AND channel_id = ? " + \
            u"AND id NOT IN (SELECT metadata_id FROM MetaDataTorrent) " + \
            u"AND id NOT IN (SELECT metadata_id FROM MetaDataPlaylist) " + \
            u"AND dispersy_id not in (SELECT cause FROM Moderations " + \
            u"WHERE channel_id = ?) ORDER BY prev_global_time DESC",
            (type_id, self._channel_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    def _get_latest_modification_from_torrent_id(self, channeltorrent_id, type_id):
        assert isinstance(channeltorrent_id, (int, long)), "channeltorrent_id type is '%s'" % type(channeltorrent_id)
        assert isinstance(type_id, (int, long)), "type_id type is '%s'" % type(type_id)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time " + \
                                                         u"FROM ChannelMetaData, MetaDataTorrent " + \
                                                         u"WHERE ChannelMetaData.id = MetaDataTorrent.metadata_id " + \
                                                         u"AND type_id = ? AND channeltorrent_id = ? " + \
                                                         u"AND dispersy_id not in " + \
                                                         u"(SELECT cause FROM Moderations WHERE channel_id = ?) " + \
                                                         u"ORDER BY prev_global_time DESC",
            (type_id, channeltorrent_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    def _get_latest_modification_from_playlist_id(self, playlist_id, type_id):
        assert isinstance(playlist_id, (int, long)), "playlist_id type is '%s'" % type(playlist_id)
        assert isinstance(type_id, (int, long)), "type_id type is '%s'" % type(type_id)

        # 1. get the dispersy identifier from the channel_id
        dispersy_ids = self._channelcast_db._db.fetchall(u"SELECT dispersy_id, prev_global_time " + \
                                                         u"FROM ChannelMetaData, MetaDataPlaylist " + \
                                                         u"WHERE ChannelMetaData.id = MetaDataPlaylist.metadata_id " + \
                                                         u"AND type_id = ? AND playlist_id = ? " + \
                                                         u"AND dispersy_id not in " + \
                                                         u"(SELECT cause FROM Moderations WHERE channel_id = ?) " + \
                                                         u"ORDER BY prev_global_time DESC",
            (type_id, playlist_id, self._channel_id))
        return self._determine_latest_modification(dispersy_ids)

    @warnDispersyThread
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

    @warnDispersyThread
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
