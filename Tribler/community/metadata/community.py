import binascii
import json
import logging

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

    def initialize(self, integrate_with_tribler=True):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._integrate_with_tribler = integrate_with_tribler

        if self._integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import MetadataDBHandler, TorrentDBHandler
            # tribler channelcast database
            self._metadata_db = MetadataDBHandler.getInstance()
            self._torrent_db = TorrentDBHandler.getInstance()
        else:
            self._metadata_db = MetadataDBStub(self._dispersy)

        super(MetadataCommunity, self).initialize()

    @classmethod
    def get_master_members(cls, dispersy):
# generated: Tue Jul 29 17:03:28 2014
# curve: NID_sect571r1
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000400dd38ab50c9fe890ecee3ba62160b04005daf493f342d974989a6ebc1ce5203204b22835ebe613ecd4b83d20639dd7607fccc8f70d09ad930689066c597b23ba8f567bff13f32c9053928baa4660b3ce725bb0f773044befeed3a5fb6367cef40542980767d9ebc0ac7d1d96e2dbdc6d65d0a7694684b18fe396d81723bd518f4d5ba5e579d5f4750c4132137ce1a8d
# pub-sha1 e625e8177ce1f344fc4be72bada996a8ff0220f3
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQA3TirUMn+iQ7O47piFgsEAF2vST80
# LZdJiabrwc5SAyBLIoNevmE+zUuD0gY53XYH/MyPcNCa2TBokGbFl7I7qPVnv/E/
# MskFOSi6pGYLPOcluw93MES+/u06X7Y2fO9AVCmAdn2evArH0dluLb3G1l0KdpRo
# Sxj+OW2BcjvVGPTVul5XnV9HUMQTITfOGo0=
# -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000400dd38ab50c9fe890ecee3ba62160b04005daf493f342d974989a6ebc1ce5203204b22835ebe613ecd4b83d20639dd7607fccc8f70d09ad930689066c597b23ba8f567bff13f32c9053928baa4660b3ce725bb0f773044befeed3a5fb6367cef40542980767d9ebc0ac7d1d96e2dbdc6d65d0a7694684b18fe396d81723bd518f4d5ba5e579d5f4750c4132137ce1a8d".decode("HEX")
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


    def create_metadata_message(self, infohash, roothash, data_list):
        columns = ("previous_global_time", "previous_mid", "this_global_time", "this_mid", "message_id")
        result_list = self._metadata_db.getMetadataMessageList(
            infohash, roothash, columns)

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
                    self._logger.warn("Duplicate key in new and old data-list: %s", data[0])
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
                            payload=(infohash, roothash, merged_data_list,
                                prev_mid, prev_global_time))
        self.__log(-1, message)
        self._dispersy.store_update_forward([message], True, True, True)


    def check_metadata(self, messages):
        for message in messages:
            # do not test downloading thumbnails in dispersy tests
            if not self._integrate_with_tribler:
                yield message
                continue

            infohash = message.payload.infohash
            roothash = message.payload.roothash

            if infohash:
                do_continue = False
                for key, value in message.payload.data_list:
                    if key.startswith("swift-"):
                        data_type = key.split('-', 1)[1]

                        _, roothash, contenthash = json.loads(value)
                        roothash = binascii.unhexlify(roothash)
                        contenthash = binascii.unhexlify(contenthash)

                        from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
                        th_handler = RemoteTorrentHandler.getInstance()
                        if not th_handler.has_metadata(data_type, infohash, contenthash):
                            self._logger.debug("Will try to download %s with roothash %s from %s",
                                key, roothash.encode("HEX"), message.candidate.sock_addr[0])

                            @call_on_reactor_thread
                            def callback(_, message=message):
                                self.on_messages([message])

                            th_handler.download_metadata(data_type, message.candidate,
                                roothash, infohash, contenthash,
                                timeout=CANDIDATE_WALK_LIFETIME, usercallback=callback)
                            do_continue = True
                            break

                        else:
                            self._logger.debug("Don't need to download swift-thumbs with roothash %s from %s, already on disk", roothash.encode("HEX"), message.candidate.sock_addr[0])

                if do_continue:
                    continue

            yield message


    def on_metadata(self, messages):
        # DO NOTHING
        pass

    def __log(self, count, message, info_str=None):
        prev_global_time = None
        prev_mid = None
        if message.payload.prev_mid:
            prev_global_time = message.payload.prev_global_time
            prev_mid = binascii.hexlify(message.payload.prev_mid)[:7]
        global_time = message.distribution.global_time
        mid = binascii.hexlify(message.authentication.member.mid)[:7]
        if message.payload.infohash:
            infohash = binascii.hexlify(message.payload.infohash)[:7]
        else:
            infohash = None
        if message.payload.roothash:
            roothash = binascii.hexlify(message.payload.roothash)[:7]
        else:
            roothash = None

        if count == 0:
            self._logger.debug("ACCEPT ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s %s]",
                message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                global_time, mid, prev_global_time, prev_mid, infohash, roothash)
        elif count == -1:
            self._logger.debug("CREATE member[%s %s] msg[(%s %s)->(%s %s)]",
                global_time, mid, prev_global_time, prev_mid, infohash, roothash)
        elif count == -2:
            self._logger.debug("IGNORE ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s %s]",
                message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                global_time, mid, prev_global_time, prev_mid, infohash, roothash)
        elif count >= 100:
            self._logger.debug("CUSTOM ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s %s] | %s",
                message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                global_time, mid, prev_global_time, prev_mid, infohash, roothash, info_str)
        else:
            self._logger.debug("DROP[%d] ip[%s:%s] member[(%s %s)->(%s %s)] msg[%s %s]",
                count, message.candidate.sock_addr[0], message.candidate.sock_addr[1],
                global_time, mid, prev_global_time, prev_mid, infohash, roothash)

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
                times[message.authentication.member.database_id] = [global_time for global_time, in self._dispersy._database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (message.community.database_id, message.authentication.member.database_id, message.database_id))]
                # assert len(times[message.authentication.member.database_id]) <= message.distribution.history_size, [message.packet_id, message.distribution.history_size, times[message.authentication.member.database_id]]

            tim = times[message.authentication.member.database_id]

            if message.distribution.global_time in tim and \
                    self._dispersy._is_duplicate_sync_message(message):
                self.__log(2, message)
                return DropMessage(message, "duplicate message by member^global_time (3)")

            # select the metadata messages from DB
            message_list = self._metadata_db.getMetadataMessageList(
                message.payload.infohash, message.payload.roothash,
                ("previous_global_time", "previous_mid",
                 "this_global_time", "this_mid", "dispersy_id"))

            if message.payload.prev_mid:
                prev_mid = message.payload.prev_mid
                prev_global_time = message.payload.prev_global_time
                this_message = (prev_global_time, prev_mid,
                    message.distribution.global_time,
                    message.authentication.member.mid, None)
            else:
                this_message = (None, None, message.distribution.global_time,
                    message.authentication.member.mid, None)

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
                                u"SELECT packet FROM sync WHERE id = ?",
                                    (message_list[-1][-1],)).next()
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
            to_clear_set.add((message.payload.infohash, message.payload.roothash))

            dispersy_id = message.packet_id
            this_global_time = message.distribution.global_time
            this_mid = message.authentication.member.mid

            # insert new metadata message
            message_id = self._metadata_db.addAndGetIDMetadataMessage(
                dispersy_id, this_global_time, this_mid,
                message.payload.infohash, message.payload.roothash,
                message.payload.prev_mid, message.payload.prev_global_time)

            # new metadata data to insert
            for key, value in message.payload.data_list:
                value_list.append((message_id, key, value))

        self._metadata_db.addMetadataDataInBatch(value_list)

        # STEP 2: cleanup and update metadataData
        sync_id_list = []
        for to_clear_infohash, to_clear_roothash in to_clear_set:
            message_list = self._metadata_db.getMetadataMessageList(
                to_clear_infohash, to_clear_roothash,
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
        self._logger = logging.getLogger(self.__class__.__name__)

        self._dispersy = dispersy

        # the dirty way: simulate the database with lists
        self._auto_message_id = 1
        self._metadata_message_db_list = []
        self._metadata_data_db_list = []


    def getAllMetadataMessage(self):
        return self._metadata_message_db_list


    def getMetadataMessageList(self, infohash, roothash, columns):
        message_list = []
        for data in self._metadata_message_db_list:
            if data["infohash"] != infohash or data["roothash"] != roothash:
                continue

            message = []
            for column in columns:
                message.append(data[column])

            message_list.append(tuple(message))

        return message_list


    def addAndGetIDMetadataMessage(self, dispersy_id, this_global_time, this_mid,
            infohash, roothash, prev_mid=None, prev_global_time=None):
        data = {"message_id": self._auto_message_id,
                "dispersy_id": dispersy_id,
                "this_global_time": this_global_time,
                "this_mid": this_mid,
                "infohash": infohash,
                "roothash": roothash,
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
                    "data_value": value_tuple[2]
            }
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
