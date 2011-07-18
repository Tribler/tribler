from conversion import Conversion
from payload import TextPayload

from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import CommunityDestination
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.distribution import FullSyncDistribution, LastSyncDistribution
from Tribler.Core.dispersy.message import Message, DropMessage
from Tribler.Core.dispersy.resolution import LinearResolution

from Tribler.Core.Statistics.Status.NullReporter import NullReporter
from Tribler.Core.Statistics.Status.Status import get_status_holder
from Tribler.Core.Statistics.Status.TUDelftReporter import TUDelftReporter

REPORTER_NAME = "Periodically flush events to TUDelft"

if __debug__:
    from Tribler.Core.dispersy.dprint import dprint

class SimpleDispersyTestCommunity(Community):
    # Identifier used for 5.3.8 debugging
    # hardcoded_cid = "f68d3d6362874fb72df6df699bd5f3967e9ed69d".decode("HEX")
    # hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b81040027038192000400ea5f524615d38be3ccacdcbc23215a23646465fbf5f10c5f775e67590df400a518f64551f16b5dad595c4476c02dbcb87ea6904fddeee7fd0a13a86e376d885ebc7e2f82638d3604ccb2c7ff24da732cdf5878aacfde45ed39087379d5448dd0a5fea775ebf776ff742363155149af58a2194f8b64c8408247a01814382a847135395ead1386b1b49dc10b2e05273d".decode("HEX")

    # Identifier used for 5.3.8 release
    # hardcoded_cid = "d4137315a3c47d65500e778448137240ff5df069".decode("HEX")
    # hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b81040027038192000401dd2eef5aba6f772aa68c7d0ecc5e2790afba9d73eb357ca1bb07ded6a57ea952d871c966e3a747174298cb89931c1c7b424a9ef44d02fcdb8f7ce0ae4e8799907b815145d4fb5b03f594f386b174ffdcfcf194ddbed45ae8f59f84a7e1f0beea9fe653cf8908649f502e68a7e9a31c75ba742d4a938cd07ec20773573d74c7f725b114c6967c55e43eb425ac52ccf8".decode("HEX")

    # Identifier used for 5.3.9 debugging
    hardcoded_cid = "8e75464d477377511a4b539b52c6a5edb10cd141".decode("HEX")
    hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004064eb30fe074b12625bb28f29b66824dca5bfad4365da9449236fa3d95ad41eb97e8f510897b25ee3752754fe39f80172f269692a8fedfb4b1f917692383ee1761c529d99e060c4b019caa00bfd61162dbcb4cdd11301eb2e681dace57266764d20953fdeb97afc199b044fda7bbc122a4ada4a102a084b8802a9f8bd9d553818fb38c3409de041355d285790c30d2f4".decode("HEX")

    @classmethod
    def join_hardcoded_community(cls, my_member):
        # ensure that the community has not already been loaded (as a HardKilledCommunity)
        if not Dispersy.get_instance().has_community(cls.hardcoded_cid):
            return cls.join_community(cls.hardcoded_cid, cls.hardcoded_master_public_key, my_member)

    @classmethod
    def load_hardcoded_community(cls):
        # ensure that the community has not already been loaded (as a HardKilledCommunity)
        if not Dispersy.get_instance().has_community(cls.hardcoded_cid):
            return cls.load_community(cls.hardcoded_cid, cls.hardcoded_master_public_key)

    def __init__(self, cid, master_public_key):
        super(SimpleDispersyTestCommunity, self).__init__(cid, master_public_key)
        if __debug__: dprint(self._cid.encode("HEX"))

        self._status = get_status_holder("dispersy-simple-dispersy-test")
        self._status.add_reporter(TUDelftReporter(REPORTER_NAME, 300, self._my_member.public_key))
        self._status.create_and_add_event("__init__^" + self._cid.encode("HEX"), ["full-sync", "last-1-sync"])
        self._status.create_and_add_event("info^" + self._cid.encode("HEX"), [self._dispersy.info()])
        self._status.report_now()
        self._dispersy.callback.register(self._periodically_info, delay=60.0)

    def initiate_meta_messages(self):
        return [Message(self, u"full-sync", MemberAuthentication(encoding="sha1"), LinearResolution(), FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", priority=128), CommunityDestination(node_count=1), TextPayload(), self.check_full_sync, self.on_full_sync, delay=5.0),
                Message(self, u"last-1-sync", MemberAuthentication(encoding="sha1"), LinearResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"in-order", priority=128, history_size=1), CommunityDestination(node_count=1), TextPayload(), self.check_last_1_sync, self.on_last_1_sync, delay=5.0)]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def dispersy_cleanup_community(self, message):
        if __debug__: dprint(self._cid.encode("HEX"))
        self._status.create_and_add_event("dispersy_cleanup_community^" + self._cid.encode("HEX") , [("is_soft_kill", message.payload.is_soft_kill), ("is_hard_kill", message.payload.is_hard_kill)])
        self._status.report_now()
        self._status.get_reporter(REPORTER_NAME).stop()
        self._status.remove_reporter(REPORTER_NAME)
        self._status.add_reporter(NullReporter("Periodically remove all events", 60))

        # will reclassify to SoftKilledCommunity or HardKilledCommunity
        return super(SimpleDispersyTestCommunity, self).dispersy_cleanup_community(message)

    def create_full_sync(self, text):
        if __debug__: dprint(self._cid.encode("HEX"))
        assert isinstance(text, unicode)
        meta = self.get_meta_message(u"full-sync")
        message =  meta.implement(meta.authentication.implement(self._my_member),
                                  meta.distribution.implement(self.claim_global_time()),
                                  meta.destination.implement(),
                                  meta.payload.implement(text))
        self._dispersy.store_update_forward([message], True, True, True)
        return message

    def check_full_sync(self, messages):
        if __debug__: dprint(self._cid.encode("HEX"))
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage(message, "TODO: implement delay by proof")
                continue
            yield message

    def on_full_sync(self, messages):
        if __debug__: dprint(self._cid.encode("HEX"))
        self._status.create_and_add_event("on_full_sync^" + self._cid.encode("HEX") , [(message.address, message.distribution.global_time, message.payload.text) for message in messages])

    def create_last_1_sync(self, text):
        if __debug__: dprint(self._cid.encode("HEX"))
        assert isinstance(text, unicode)
        meta = self.get_meta_message(u"last-1-sync")
        message = meta.implement(meta.authentication.implement(self._my_member),
                                 meta.distribution.implement(self.claim_global_time()),
                                 meta.destination.implement(),
                                 meta.payload.implement(text))
        self._dispersy.store_update_forward([message], True, True, True)
        return message

    def check_last_1_sync(self, messages):
        if __debug__: dprint(self._cid.encode("HEX"))
        for message in messages:
            if not self._timeline.check(message):
                yield DropMessage(message, "TODO: implement delay by proof")
                continue
            yield message

    def on_last_1_sync(self, messages):
        if __debug__: dprint(self._cid.encode("HEX"))
        self._status.create_and_add_event("on_last_1_sync^" + self._cid.encode("HEX"), [(message.address, message.distribution.global_time, message.payload.text) for message in messages])

    def _periodically_info(self):
        while True:
            self._status.create_and_add_event("info^" + self._cid.encode("HEX"), [self._dispersy.info(attributes=False)])
            yield 60.0

