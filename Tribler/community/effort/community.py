from conversion import EffortConversion
from database import EffortDatabase
from payload import EffortRecordPayload
from efforthistory import CYCLE_SIZE, EffortHistory

from Tribler.Core.dispersy.candidate import BootstrapCandidate
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.message import BatchConfiguration, Message
from Tribler.Core.dispersy.authentication import MultiMemberAuthentication
from Tribler.Core.dispersy.resolution import PublicResolution
from Tribler.Core.dispersy.distribution import LastSyncDistribution
from Tribler.Core.dispersy.destination import CommunityDestination

from time import time

from Tribler.Core.dispersy.dprint import dprint
from lencoder import bz2log, close

class EffortCommunity(Community):
    def __init__(self, master, class_):
        # original walker callbacks (will be set during super(...).__init__)
        self._original_on_introduction_request = None
        self._original_on_introduction_response = None

        super(EffortCommunity, self).__init__(master)

        # storage
        self._database = EffortDatabase.get_instance(self._dispersy.working_directory)

        # cache
        self._histories = dict()

        # periodic tasks
        self._pending_callbacks.append(self._dispersy.callback.register(self._watchdog))

        # log
        bz2log("effort.log", "load", my_member=self._my_member.mid, class_=class_, cycle_size=CYCLE_SIZE)

    def initiate_meta_messages(self):
        return [Message(self, u"effort-record", MultiMemberAuthentication(count=2, allow_signature_func=self.allow_signature_request), PublicResolution(), LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1), CommunityDestination(node_count=10), EffortRecordPayload(), self.check_effort_record, self.on_effort_record, batch=BatchConfiguration(max_window=4.5)),
                ]

    def _initialize_meta_messages(self):
        super(EffortCommunity, self)._initialize_meta_messages()

        # replace the callbacks for the dispersy-introduction-request and
        # dispersy-introduction-response messages
        meta = self._meta_messages[u"dispersy-introduction-request"]
        self._original_on_introduction_request = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_request, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_request

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_response, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_response

    def initiate_conversions(self):
        return [DefaultConversion(self), EffortConversion(self)]

    @staticmethod
    def flush_log():
        close("effort.log")

    def _watchdog(self):
        while True:
            try:
                desync = (yield 60.0)

                # flush changes to disk every 1 minutes
                self._database.commit()
            except GeneratorExit:
                bz2log("effort.log", "unload")
                if __debug__: dprint("shutdown")
                self._database.commit()
                break

    def _get_or_create_history(self, member, now):
        if __debug__:
            if member in self._histories:
                dprint("member in histories (", member.mid.encode("HEX"), ", ", bin(self._histories[member].long), ")")
            else:
                dprint("member NOT in histories")
        try:
            return self._histories[member]
        except KeyError:
            try:
                timestamp, bytes_ = self._database.execute(u"SELECT timestamp, effort FROM observation WHERE community = ? AND member = ?",
                                                           (self._database_id, member.database_id)).next()
            except StopIteration:
                self._histories[member] = history = EffortHistory(8*64, now)
            else:
                self._histories[member] = history = EffortHistory(bytes_, len(bytes) * 8, float(timestamp))
            return history

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            now = time()
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    for member in message.candidate.get_members(self):
                        history = self._get_or_create_history(member, now)
                        changed = history.set(now)
                        if __debug__: dprint("introduction-request from ", message.candidate, " - ", bin(history.long))

                        # if changed:
                        #     if __debug__: dprint("changed! (", member.mid.encode("HEX"), ", ", bin(self._histories[member].long), ")")
                        #     self.create_effort_record(member, history)

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            now = time()
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    for member in message.candidate.get_members(self):
                        history = self._get_or_create_history(member, now)
                        changed = history.set(now)
                        if __debug__: dprint("introduction-response from ", message.candidate, " - ", bin(history.long))

                        if changed:
                            if __debug__: dprint("changed! (", member.mid.encode("HEX"), ", ", bin(self._histories[member].long), ")")
                            self.create_effort_record(member, history)

    def create_effort_record(self, second_member, history, forward=True):
        """
        Create a dispersy-signature-request that encapsulates an effort-record.
        """
        if __debug__: dprint(second_member.mid.encode("HEX"), " = ", bin(history.long))

        meta = self.get_meta_message(u"effort-record")
        record = meta.impl(authentication=([self._my_member, second_member],),
                           distribution=(self.claim_global_time(),),
                           payload=(history.origin, 0.0, history))
        return self.create_dispersy_signature_request(record, self.on_signature_response, forward=forward)

    def allow_signature_request(self, message):
        """
        A dispersy-signature-request has been received.

        Return None or a Message.Implementation.
        """
        assert message.name == u"effort-record"
        assert not message.authentication.is_signed
        if __debug__: dprint(message)

        _, first_member = message.authentication.signed_members[0]
        _, second_member = message.authentication.signed_members[1]
        global_time = message.distribution.global_time if message.distribution.global_time <= self.global_time else self.claim_global_time()

        if first_member == self._my_member:
            local_history = self._get_or_create_history(second_member, time())
            first_timestamp = local_history.origin
            second_timestamp = message.payload.second_timestamp

        else:
            assert second_member == self._my_member
            local_history = self._get_or_create_history(first_member, time())
            first_timestamp = message.payload.first_timestamp
            second_timestamp = local_history.origin

        if __debug__: dprint("time diff:", abs(first_timestamp - second_timestamp), "; bits diff:", local_history.long ^ message.payload.history.long)

        # TODO shift history and origin for a match
        history = EffortHistory(local_history.long & message.payload.history.long, local_history.size, local_history.origin)

        bz2log("effort.log", "diff", local=bin(history.long), remote=bin(message.payload.history.long), propose=bin(history.long), time_diff=int(abs(first_timestamp - second_timestamp)))

        # return the modified effort-record we propose
        meta = self.get_meta_message(u"effort-record")
        return meta.impl(authentication=([first_member, second_member],),
                         distribution=(global_time,),
                         payload=(first_timestamp, second_timestamp, history))

    def on_signature_response(self, old_message, new_message, changed):
        """
        A dispersy-signature-response has been received.

        Return True or False to either accept or decline the message.
        """
        if __debug__: dprint(new_message)

        if new_message:
            if old_message.meta == new_message.meta:
                return True, True, False

        return False, False, False

    def check_effort_record(self, messages):
        # stupidly accept everything...
        return messages

    def on_effort_record(self, messages):
        if __debug__: dprint("storing ", len(messages), " effort records")
        for message in messages:
            bz2log("effort.log", "effort-record", global_time=message.distribution.global_time, first_member=message.authentication.members[0].mid, second_member=message.authentication.members[1].mid, first_timestamp=int(message.payload.first_timestamp), second_timestamp=int(message.payload.second_timestamp), bits=message.payload.history.long)
        self._database.executemany(u"INSERT OR REPLACE INTO record (community, global_time, first_member, second_member, first_timestamp, second_timestamp, effort) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   ((self._database_id, message.distribution.global_time, message.authentication.members[0].database_id, message.authentication.members[1].database_id, int(message.payload.first_timestamp), int(message.payload.second_timestamp), buffer(message.payload.history.bytes)) for message in messages))
