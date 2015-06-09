import binascii
import json

from Tribler.Core.Utilities.twisted_thread import callInThreadPool
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.util import call_on_reactor_thread

from conversion import MetadataConversion
from payload import MetadataPayload


class MetadataCommunity(Community):

    def __init__(self, *args, **kwargs):
        super(MetadataCommunity, self).__init__(*args, **kwargs)

        self.tribler_session = None
        self._integrate_with_tribler = None

        self._metadata_db = None
        self._torrent_db = None
        self._rth = None

    def initialize(self, tribler_session=None):
        self.tribler_session = tribler_session
        self._integrate_with_tribler = tribler_session is not None

        if self._integrate_with_tribler:
            from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_METADATA
            # tribler channelcast database
            self._metadata_db = self.tribler_session.open_dbhandler(NTFY_METADATA)
            self._torrent_db = self.tribler_session.open_dbhandler(NTFY_TORRENTS)

            self._rth = self.tribler_session.lm.rtorrent_handler

        else:
            self._metadata_db = MetadataDBStub(self._dispersy)

        super(MetadataCommunity, self).initialize()

    @classmethod
    def get_master_members(cls, dispersy):
# generated: Sat Dec 13 22:44:37 2014
# curve: NID_sect571r1
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b810400270381920004020909beb5c67aa72f63bf988c3f4ff252abf0d2c57e22e782298390502a887d422d7737ef477f6de747ed1f10fdff414740e488a1c476357bc19feead19ce86cfd7d0c48ea545c205ce2651b359d6d986b7b975757aab75ef9862a96246a31e6e55a55855b581b0b579504ce346f1d16d9a639e87aba92a4b809650b822789d45360f856cd9d1e5aaee2de02dc39e81
# pub-sha1 a85a5394532a0612d2076e9d54fcb0dda13c5520
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQCCQm+tcZ6py9jv5iMP0/yUqvw0sV+
# IueCKYOQUCqIfUItdzfvR39t50ftHxD9/0FHQOSIocR2NXvBn+6tGc6Gz9fQxI6l
# RcIFziZRs1nW2Ya3uXV1eqt175hiqWJGox5uVaVYVbWBsLV5UEzjRvHRbZpjnoer
# qSpLgJZQuCJ4nUU2D4Vs2dHlqu4t4C3DnoE=
# -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004020909beb5c67aa72f63bf988c3f4ff252abf0d2c57e22e782298390502a887d422d7737ef477f6de747ed1f10fdff414740e488a1c476357bc19feead19ce86cfd7d0c48ea545c205ce2651b359d6d986b7b975757aab75ef9862a96246a31e6e55a55855b581b0b579504ce346f1d16d9a639e87aba92a4b809650b822789d45360f856cd9d1e5aaee2de02dc39e81".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    @property
    def dispersy_sync_skip_enable(self):
        return self._integrate_with_tribler

    @property
    def dispersy_sync_cache_enable(self):
        return self._integrate_with_tribler

    def initiate_conversions(self):
        return [DefaultConversion(self), MetadataConversion(self)]

    def initiate_meta_messages(self):
        custom_callback = (self.custom_callback_check, self.custom_callback_store)
        return super(MetadataCommunity, self).initiate_meta_messages() + [
            Message(self, u"metadata", MemberAuthentication(),
                    PublicResolution(),
                    LastSyncDistribution(synchronization_direction=u"DESC",
                                         priority=128,
                                         history_size=1,
                                         custom_callback=custom_callback),
                    CommunityDestination(node_count=10),
                    MetadataPayload(),
                    self.check_metadata,
                    self.on_metadata),
        ]

    def create_metadata_message(self, infohash, data_list):
        columns = (u"previous_global_time", u"previous_mid", u"this_global_time", u"this_mid", u"message_id")
        result_list = self._metadata_db.getMetadataMessageList(infohash, columns)

        prev_mid = None
        prev_global_time = None
        merged_data_list = data_list
        if result_list:
            result_list.sort()
            prev_global_time = result_list[-1][2]
            prev_mid = result_list[-1][3]

            # merge data-list
            message_id = result_list[-1][-1]
            prev_data_list = self._metadata_db.getMetadataData(message_id)

            merged_data_set = set(data_list)
            # check duplicates
            for data in prev_data_list:
                if data in merged_data_set:
                    self._logger.warn(u"Duplicate key in new and old data-list: %s", data[0])
            # merge
            merged_data_set.update(prev_data_list)
            merged_data_list = list(merged_data_set)

            # shrink the values to <= 1KB
            for idx in xrange(len(merged_data_list)):
                if len(merged_data_list[idx][1]) > 1024:
                    merged_data_list[idx] = (merged_data_list[idx][0], merged_data_list[idx][1][:1024])

        meta = self.get_meta_message(u"metadata")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(infohash, merged_data_list, prev_mid, prev_global_time))
        self.__log(-1, message)
        self._dispersy.store_update_forward([message], True, True, True)

    def check_metadata(self, messages):
        for message in messages:
            # do not test downloading thumbnails in dispersy tests
            if not self._integrate_with_tribler:
                yield message
                continue

            infohash = message.payload.infohash

            if infohash:
                do_continue = False
                for key, value in message.payload.data_list:
                    if key == u"swift-thumbs":
                        _, sub_file_path, thumbnail_hash_str = json.loads(value)

                        if not self._rth.has_metadata(infohash, sub_file_path):
                            self._logger.debug(u"try to download %s key=%s with %s from %s", thumbnail_hash_str, key,
                                               message.candidate.sock_addr[0], message.candidate.sock_addr[1])

                            @call_on_reactor_thread
                            def callback(_, msg=message):
                                self.on_messages([msg])
                                msg_metadata = {u"infohash": msg.payload.infohash,
                                                u"data_list": msg.payload.data_list[:]
                                                }
                                if self._integrate_with_tribler:
                                    callInThreadPool(self._check_metadata_thumbs, msg_metadata)

                            self._rth.download_metadata(message.candidate, infohash, sub_file_path,
                                                        timeout=CANDIDATE_WALK_LIFETIME, usercallback=callback)
                            do_continue = True
                            break

                        else:
                            self._logger.debug(u"metadata %s already on disk, no need to download from %s:%s",
                                               thumbnail_hash_str,
                                               message.candidate.sock_addr[0], message.candidate.sock_addr[1])

                if do_continue:
                    continue

            yield message

    def _check_metadata_thumbs(self, metadata):
        from Tribler.Core.Video.VideoUtility import considered_xxx

        # check the thumbnails if they are good
        infohash = metadata[u"infohash"]
        for key, value in metadata[u"data_list"]:
            if key != u"swift-thumbs":
                continue

            _, sub_file_path, thumbnail_hash_str = json.loads(value)

            # check if there is xxx thumbnail
            metadata_filepath = self._rth.get_metadata_path(infohash, sub_file_path)
            if considered_xxx(metadata_filepath):
                # delete the thumbnails if the family filter is enabled
                self._rth.delete_metadata(infohash, thumbnail_hash_str)
                break

    def on_metadata(self, messages):
        pass

    def __log(self, count, message, info_str=None):
        prev_global_time = None
        prev_mid = None
        if message.payload.prev_mid:
            prev_global_time = message.payload.prev_global_time
            prev_mid = binascii.hexlify(message.payload.prev_mid)[:7]
        global_time = message.distribution.global_time
        mid = binascii.hexlify(message.authentication.member.mid)[:7]
        infohash = binascii.hexlify(message.payload.infohash)[:7] if message.payload.infohash else None

        if count == 0:
            self._logger.debug(u"ACCEPT ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s]",
                               message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                               global_time, mid, prev_global_time, prev_mid, infohash)
        elif count == -1:
            self._logger.debug(u"CREATE member[(%s %s)->(%s %s)] msg[%s]",
                               global_time, mid, prev_global_time, prev_mid, infohash)
        elif count == -2:
            self._logger.debug(u"IGNORE ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s]",
                               message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                               global_time, mid, prev_global_time, prev_mid, infohash)
        elif count >= 100:
            self._logger.debug(u"CUSTOM ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s] | %s",
                               message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                               global_time, mid, prev_global_time, prev_mid, infohash, info_str)
        else:
            self._logger.debug(u"DROP[%d] ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s]",
                               count, message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                               global_time, mid, prev_global_time, prev_mid, infohash)

    def custom_callback_check(self, unique, times, message):
        """
        Checks if we drop this message or not. We update the metadata with
        the following rules:
          (1) UNIQUE: If we have received this message before. (DROP)
          (2) NEW METADATA BEFORE FULL: The number of metadata for the same
              object has not reached the maximum number X and there is no previous
              metadata. If not we DROP.
        """
        assert isinstance(unique, set)
        assert isinstance(times, dict)
        assert isinstance(message, Message.Implementation)
        # check UNIQUE
        key = (message.authentication.member.database_id, message.distribution.global_time)
        if key in unique:
            self.__log(1, message)
            return DropMessage(message, u"already processed message by member^global_time")

        else:
            unique.add(key)

            if not message.authentication.member.database_id in times:
                times[message.authentication.member.database_id] = \
                    [global_time for global_time, in self._dispersy._database.execute(
                        u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?",
                        (message.community.database_id,
                         message.authentication.member.database_id, message.database_id))]
                # assert len(times[message.authentication.member.database_id]) <= message.distribution.history_size, [message.packet_id, message.distribution.history_size, times[message.authentication.member.database_id]]

            tim = times[message.authentication.member.database_id]

            if message.distribution.global_time in tim and self._dispersy._is_duplicate_sync_message(message):
                self.__log(2, message)
                return DropMessage(message, "duplicate message by member^global_time (3)")

            # select the metadata messages from DB
            message_list = self._metadata_db.getMetadataMessageList(
                message.payload.infohash,
                (u"previous_global_time", u"previous_mid", u"this_global_time", u"this_mid", u"dispersy_id"))

            if message.payload.prev_mid:
                prev_mid = message.payload.prev_mid
                prev_global_time = message.payload.prev_global_time
                this_message = (prev_global_time, prev_mid,
                                message.distribution.global_time, message.authentication.member.mid, None)
            else:
                this_message = (None, None, message.distribution.global_time, message.authentication.member.mid, None)

            # compare previous pointers
            if message_list:
                message_list.append(this_message)
                message_list.sort()

                # This message be in the top X in order to be stored, otherwise
                # it is an old message and we send back our latest one.
                history_size = message.distribution.history_size
                history_size = 1 if history_size < 1 else history_size
                if this_message not in message_list[-history_size:]:
                    # dirty way
                    if message.distribution.history_size == 1:
                        # send the latest message to the sender
                        try:
                            packet, = self._dispersy._database.execute(
                                u"SELECT packet FROM sync WHERE id = ?", (message_list[-1][-1],)).next()
                        except StopIteration:
                            pass
                        else:
                            self._dispersy._send_packets([message.candidate], [str(packet)],
                                                         self, "-caused by custom-check-lastdist-")

                    self.__log(3, message)
                    return DropMessage(message, u"This metadata message is old.")

            self.__log(0, message)
            return message

    def custom_callback_store(self, messages):
        """
        Store everything into MetadataMessage table and MetadataData table.

        Return a list of SyncIDs (dispersy IDs) with need to be removed from
        the dispersy sync table.
        """
        # STEP 1: insert everything
        to_clear_set = set()
        value_list = []
        for message in messages:
            to_clear_set.add(message.payload.infohash)

            dispersy_id = message.packet_id
            this_global_time = message.distribution.global_time
            this_mid = message.authentication.member.mid

            # insert new metadata message
            message_id = self._metadata_db.addAndGetIDMetadataMessage(
                dispersy_id, this_global_time, this_mid,
                message.payload.infohash, message.payload.prev_mid, message.payload.prev_global_time)

            # new metadata data to insert
            for key, value in message.payload.data_list:
                value_list.append((message_id, key, value))

        self._metadata_db.addMetadataDataInBatch(value_list)

        # STEP 2: cleanup and update metadataData
        sync_id_list = []
        for to_clear_infohash in to_clear_set:
            message_list = self._metadata_db.getMetadataMessageList(
                to_clear_infohash,
                ("previous_global_time", "previous_mid", "this_global_time", "this_mid", "dispersy_id"))

            # compare previous pointers
            if message_list:
                message_list.sort()

                for message in message_list[:-1]:
                    dispersy_id = message[-1]
                    self._metadata_db.deleteMetadataMessage(dispersy_id)

                    sync_id_list.append((dispersy_id, dispersy_id))

        return sync_id_list


class MetadataDBStub(object):

    def __init__(self, dispersy):
        self._dispersy = dispersy

        # the dirty way: simulate the database with lists
        self._auto_message_id = 1
        self._metadata_message_db_list = []
        self._metadata_data_db_list = []

    def getAllMetadataMessage(self):
        return self._metadata_message_db_list

    def getMetadataMessageList(self, infohash, columns):
        message_list = []
        for data in self._metadata_message_db_list:
            if data["infohash"] != infohash:
                continue

            message = []
            for column in columns:
                message.append(data[column])

            message_list.append(tuple(message))

        return message_list

    def addAndGetIDMetadataMessage(self, dispersy_id, this_global_time, this_mid, infohash,
                                   prev_mid=None, prev_global_time=None):
        data = {"message_id": self._auto_message_id,
                "dispersy_id": dispersy_id,
                "this_global_time": this_global_time,
                "this_mid": this_mid,
                "infohash": infohash,
                "previous_mid": prev_mid,
                "previous_global_time": prev_global_time}
        self._metadata_message_db_list.append(data)

        this_message_id = self._auto_message_id
        self._auto_message_id += 1

        return this_message_id

    def addMetadataDataInBatch(self, value_tuple_list):
        for value_tuple in value_tuple_list:
            data = {"message_id": value_tuple[0],
                    "data_key": value_tuple[1],
                    "data_value": value_tuple[2]}
            self._metadata_data_db_list.append(data)

    def deleteMetadataMessage(self, dispersy_id):
        new_metadata_message_db_list = []
        for data in self._metadata_message_db_list:
            if data["dispersy_id"] != dispersy_id:
                new_metadata_message_db_list.append(data)
        self._metadata_message_db_list = new_metadata_message_db_list

    def getMetadataData(self, message_id):
        data_list = []
        for msg_id, key, value in self._metadata_data_db_list:
            if msg_id != message_id:
                continue
            data_list.append((key, value))
        return data_list
