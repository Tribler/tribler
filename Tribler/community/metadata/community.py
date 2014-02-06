import logging

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution

from conversion import MetadataConversion
from payload import MetadataPayload


class MetadataCommunity(Community):

    def __init__(self, dispersy, master, integrate_with_tribler=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._integrate_with_tribler = integrate_with_tribler

        super(MetadataCommunity, self).__init__(dispersy, master)

        if self._integrate_with_tribler:
            from Tribler.Core.CacheDB.SqliteCacheDBHandler import MetadataDBHandler, TorrentDBHandler
            # tribler channelcast database
            self._metadata_db = MetadataDBHandler.getInstance()
            self._torrent_db = TorrentDBHandler.getInstance()
        else:
            self._metadata_db = MetadataDBStub(self._dispersy)

    @property
    def dispersy_sync_skip_enable(self):
        return False

    @property
    def dispersy_sync_cache_enable(self):
        return False

    def initiate_conversions(self):
        return [DefaultConversion(self), MetadataConversion(self)]


    def initiate_meta_messages(self):
        custom_callback = (self.custom_callback_check, self.custom_callback_store)
        return [Message(self, u"metadata", MemberAuthentication(encoding="sha1"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1, custom_callback=custom_callback), CommunityDestination(node_count=10), MetadataPayload(), self.check_metadata, self.on_metadata),
                ]


    def create_metadata_message(self, infohash, roothash, data_list):
        columns = (u"previous_global_time", u"previous_mid", u"this_global_time", u"this_mid")
        result_list = self._metadata_db.getMetadataMessageList(
            infohash, roothash, columns)

        prev_metadata_mid = None
        prev_metadata_global_time = None
        if result_list:
            result_list.sort()
            prev_metadata_global_time = result_list[-1][2]
            prev_metadata_mid = result_list[-1][3]

        meta = self.get_meta_message(u"metadata")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            payload=(infohash, roothash, data_list, prev_metadata_mid, prev_metadata_global_time))
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
                infohash = str2bin(infohash)

                do_continue = False
                for key,value in message.payload.data_list:
                    if key == "swift-thumbnails":
                        roothash = value
                        if not th_handler.has_thumbnail(infohash, roothash):
                            self._logger.debug("Will try to download swift-thumbnails with roothash %s from %s", hex_roothash.encode("HEX"), message.candidate.sock_addr[0])

                            @forceDispersyThread
                            def callback(message=message):
                                self._dispersy.on_messages([message])

                            th_handler.download_thumbnail(message.candidate, roothash, infohash, timeout=CANDIDATE_WALK_LIFETIME, usercallback=callback)
                            do_continue = True
                            break

                        else:
                            self._logger.debug("Don't need to download swift-thumbnails with roothash %s from %s, already on disk", hex_roothash.encode("HEX"), message.candidate.sock_addr[0])

                if do_continue:
                    continue

            yield message


    def on_metadata(self, messages):
        # DO NOTHING
        pass


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
            return DropMessage(message, u"already processed message by member^global_time")

        else:
            unique.add(key)

            if not message.authentication.member.database_id in times:
                times[message.authentication.member.database_id] = [global_time for global_time, in self._dispersy._database.execute(u"SELECT global_time FROM sync WHERE community = ? AND member = ? AND meta_message = ?", (message.community.database_id, message.authentication.member.database_id, message.database_id))]
                #assert len(times[message.authentication.member.database_id]) <= message.distribution.history_size, [message.packet_id, message.distribution.history_size, times[message.authentication.member.database_id]]

            tim = times[message.authentication.member.database_id]

            if message.distribution.global_time in tim and self._dispersy._is_duplicate_sync_message(message):
                return DropMessage(message, "duplicate message by member^global_time (3)")

            # select the metadata messages from DB
            message_list = self._metadata_db.getMetadataMessageList(
                message.payload.infohash, message.payload.roothash,
                (u"previous_global_time", u"previous_mid", u"this_global_time", u"this_mid", u"dispersy_id"))

            if message.payload.prev_metadata_mid:
                prev_metadata_mid = message.payload.prev_metadata_mid
                prev_metadata_global_time = message.payload.prev_metadata_global_time
                this_message = (prev_metadata_global_time, prev_metadata_mid, message.distribution.global_time, message.authentication.member.mid, None)
            else:
                this_message = (None, None, message.distribution.global_time, message.authentication.member.mid, None)

            # compare previous pointers
            if message_list:
                message_list.append(this_message)
                message_list.sort()

                if message_list[0] == this_message:
                    # send the latest message to the sender
                    if message.distribution.history_size == 1:
                        try:
                            packet, = self._dispersy._database.execute(
                                u"SELECT packet FROM sync WHERE id = ?",
                                    (message_list[-1][-1],)).next()
                        except StopIteration:
                            pass
                        else:
                            self._dispersy._statistics.dict_inc(self._dispersy._statistics.outgoing, u"-lastdist-")
                            self._dispersy._endpoint.send([message.candidate], [str(packet)])

                    return DropMessage(message, u"This metadata message is old.")

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
                message.payload.prev_metadata_mid, message.payload.prev_metadata_global_time)

            # new metadata data to insert
            key_set = set()
            for key, value in message.payload.data_list:
                # avoid collision when inserting
                if key not in key_set:
                    key_set.add(key)
                    value_list.append((message_id, key, value))

        self._metadata_db.addMetadataDataInBatch(value_list)

        # STEP 2: cleanup and update metadataData
        sync_id_list = []
        for to_clear_infohash, to_clear_roothash in to_clear_set:
            message_list = self._metadata_db.getMetadataMessageList(
                to_clear_infohash, to_clear_roothash,
                (u"previous_global_time", u"previous_mid", u"this_global_time", u"this_mid", u"dispersy_id"))

            # compare previous pointers
            if message_list:
                message_list.sort()

                for message in message_list[:-1]:
                    dispersy_id = message[4]
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
            if data[u"infohash"] != infohash or data[u"roothash"] != roothash:
                continue

            message = []
            for column in columns:
                message.append(data[column])

            message_list.append(tuple(message))

        return message_list


    def addAndGetIDMetadataMessage(self, dispersy_id, this_global_time, this_mid,
            infohash, roothash,
            prev_metadata_mid=None, prev_metadata_global_time=None):
        data = {u"message_id": self._auto_message_id,
                u"dispersy_id": dispersy_id,
                u"this_global_time": this_global_time,
                u"this_mid": this_mid,
                u"infohash": infohash,
                u"roothash": roothash,
                u"previous_mid": prev_metadata_mid,
                u"previous_global_time": prev_metadata_global_time}
        self._metadata_message_db_list.append(data)

        this_message_id = self._auto_message_id
        self._auto_message_id += 1

        return this_message_id


    def addMetadataDataInBatch(self, value_tuple_list):
        for value_tuple in value_tuple_list:
            data = {u"message_id": value_tuple[0],
                    u"data_key": value_tuple[1],
                    u"data_value": value_tuple[2]
            }
            self._metadata_data_db_list.append(data)


    def deleteMetadataMessage(self, dispersy_id):
        new_metadata_message_db_list = []
        for data in self._metadata_message_db_list:
            if data[u"dispersy_id"] != dispersy_id:
                new_metadata_message_db_list.append(data)
        self._metadata_message_db_list = new_metadata_message_db_list
