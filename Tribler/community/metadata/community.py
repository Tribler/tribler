import logging
import json
import binascii

from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME

from conversion import MetadataConversion
from payload import MetadataPayload

from Tribler.community.channel.community import forceDispersyThread


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


    @classmethod
    def get_master_members(cls, dispersy):
# generated: Tue Mar 18 13:15:06 2014
# curve: NID_sect571r1
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040151e8244bdba89d7745139c34da401c5e53849812cff86d9bd6b93f84638e6aad44a03efb7b9a7a23b8dbf5059d5965b3ba485852df6e27c747101b7db1c1793d18efed4a90766d01ce2747dd0fe1cd2cd04d4d64a445b246189e12094685196a07d89571b179815aacd1e1bdb0b03be18b87d117f9cc5ce871be1263d995c1f5d206d99adc49e703e875c309a83704
# pub-sha1 899a565ea8c134dc62f72eff80dcb71b164522db
# -----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQBUegkS9uonXdFE5w02kAcXlOEmBLP
# +G2b1rk/hGOOaq1EoD77e5p6I7jb9QWdWWWzukhYUt9uJ8dHEBt9scF5PRjv7UqQ
# dm0BzidH3Q/hzSzQTU1kpEWyRhieEglGhRlqB9iVcbF5gVqs0eG9sLA74YuH0Rf5
# zFzocb4SY9mVwfXSBtma3EnnA+h1wwmoNwQ=
# -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040151e8244bdba89d7745139c34da401c5e53849812cff86d9bd6b93f84638e6aad44a03efb7b9a7a23b8dbf5059d5965b3ba485852df6e27c747101b7db1c1793d18efed4a90766d01ce2747dd0fe1cd2cd04d4d64a445b246189e12094685196a07d89571b179815aacd1e1bdb0b03be18b87d117f9cc5ce871be1263d995c1f5d206d99adc49e703e875c309a83704".decode("HEX")
        master = dispersy.get_member(master_key)
        return [master]

    @classmethod
    def load_community(cls, dispersy, master, my_member, integrate_with_tribler=True):
        try:
            dispersy.database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, integrate_with_tribler=integrate_with_tribler)
        else:
            return super(MetadataCommunity, cls).load_community(dispersy, master, integrate_with_tribler=integrate_with_tribler)

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
        return [Message(self, u"metadata", MemberAuthentication(encoding="sha1"), PublicResolution(), LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1, custom_callback=custom_callback), CommunityDestination(node_count=10), MetadataPayload(), self.check_metadata, self.on_metadata),
                ]


    def create_metadata_message(self, infohash, roothash, data_list):
        columns = ("previous_global_time", "previous_mid", "this_global_time", "this_mid")
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
                do_continue = False
                for key,value in message.payload.data_list:
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

                            @forceDispersyThread
                            def callback(_,message=message):
                                self._dispersy.on_messages([message])

                            th_handler.download_metadata(data_type, message.candidate, roothash, infohash, contenthash, timeout=CANDIDATE_WALK_LIFETIME, usercallback=callback)
                            do_continue = True
                            break

                        else:
                            self._logger.debug("Don't need to download swift-thumbnails with roothash %s from %s, already on disk", roothash.encode("HEX"), message.candidate.sock_addr[0])

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
                ("previous_global_time", "previous_mid", "this_global_time", "this_mid", "dispersy_id"))

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
            if data["infohash"] != infohash or data["roothash"] != roothash:
                continue

            message = []
            for column in columns:
                message.append(data[column])

            message_list.append(tuple(message))

        return message_list


    def addAndGetIDMetadataMessage(self, dispersy_id, this_global_time, this_mid,
            infohash, roothash,
            prev_metadata_mid=None, prev_metadata_global_time=None):
        data = {"message_id": self._auto_message_id,
                "dispersy_id": dispersy_id,
                "this_global_time": this_global_time,
                "this_mid": this_mid,
                "infohash": infohash,
                "roothash": roothash,
                "previous_mid": prev_metadata_mid,
                "previous_global_time": prev_metadata_global_time}
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
