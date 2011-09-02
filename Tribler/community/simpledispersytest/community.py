from random import shuffle

from conversion import Conversion
from payload import TextPayload

from Tribler.Core.dispersy.authentication import MemberAuthentication
from Tribler.Core.dispersy.community import Community
from Tribler.Core.dispersy.conversion import DefaultConversion
from Tribler.Core.dispersy.destination import SubjectiveDestination
from Tribler.Core.dispersy.dispersy import Dispersy
from Tribler.Core.dispersy.distribution import FullSyncDistribution, LastSyncDistribution
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.message import Message, DelayMessageByProof
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

    # # Identifier used for 5.3.9 debugging
    # hardcoded_cid = "8e75464d477377511a4b539b52c6a5edb10cd141".decode("HEX")
    # hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004064eb30fe074b12625bb28f29b66824dca5bfad4365da9449236fa3d95ad41eb97e8f510897b25ee3752754fe39f80172f269692a8fedfb4b1f917692383ee1761c529d99e060c4b019caa00bfd61162dbcb4cdd11301eb2e681dace57266764d20953fdeb97afc199b044fda7bbc122a4ada4a102a084b8802a9f8bd9d553818fb38c3409de041355d285790c30d2f4".decode("HEX")

    # # Identifier used for 5.3.9 release
    # hardcoded_cid = "d78b4ea420015eda19e376aff5016055921f4862".decode("HEX")
    # hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004048d327e2519a07a50fb3f4d6a6fc8739672b9cc309751fc5698eb96dea6df180068f53a95ccc4239387903a0af16e657f3ed1848880f7d194ffb8482fd09100fe2bed5c2810c8c505661aa8e4924fa2ccd1e9a93a86e45806e386569c70dbe25b68e2dae429355fd5407a721c3f3ae1593ed5f75278b6f4282eec7c2ec9b8553996092b5240b0cee893fa914cc4422c".decode("HEX")

    # # Identifier used for 5.4.0 debugging
    # hardcoded_cid = "b09a66118ad35c3d967d12492003b76b31807499".decode("HEX")
    # hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b81040027038192000401964308acfa0f7821be30b12d2929fba8a258da6a87aa4a76b7ae5cb23facb9ebd15b3c4cd92c3c840ca286d8dae0af77dbe7acf76c326e6e86993cf140b0f14ea64146d3936376040221bd588e51e3431f7fc33aa5bd6215065d46fe539290fec39330f5e22b3a3140ce751a74beaba6b37005d77bb0c77b64c592e82f90bfaf31d84bbe62cd3a3a966daa30754f05".decode("HEX")

    # Identifier used for 5.4.0 release
    hardcoded_cid = "cc7e0ef053e312b4939b81ad49addd683f8fded9".decode("HEX")
    hardcoded_master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004055a08de0930e7a1026c68b344377f315d149d0a17a280e5fd1ea34fd6e9a60351379cf4959ab91d2da3bc30f0de8725d4a1e470281bfceae79666126842bf1a428d3c76024f57280261a7f26f5b940da8a276c51094d2758e20f5c559b4745f4443a5dbdc4faa692e08dfbd39168b1a4d1e94bb4f3c176ba04a0bf6141dd04e0672dcd695912c26528f865d514f92a5".decode("HEX")
    hardcoded_member_public_keys = {"A":"3052301006072a8648ce3d020106052b8104001a033e000400d11dc4978f2df3e45f812bd8885cd35bbd81908f4b8889ebecb79529bf01feba5bb039dd11f25c69921a55fc66af0528e509430e656496825378a0".decode("HEX"),
                                    "B":"3052301006072a8648ce3d020106052b8104001a033e000401f6a239c56233aec58aba28f2d4b088b287fd01a2387894e5d4345974d90131fc665d2c31c27fac2a30cbdc131a2d1ec8f85998b624a01fb003d126".decode("HEX"),
                                    "C":"3052301006072a8648ce3d020106052b8104001a033e000400b407a2c022191aa1feba1cd2f7fe87bc4aad223ca638e2441a830d692101351993629a7e9a4fbbe3496daaba0d6d94f74b5f6a3bae8cef3bdd4abe".decode("HEX")}

    @classmethod
    def join_hardcoded_community(cls, my_member):
        # ensure that the community has not already been loaded (as a HardKilledCommunity)
        if not Dispersy.get_instance().has_community(cls.hardcoded_cid):
            return cls.join_community(Member.get_instance(cls.hardcoded_master_public_key), my_member)

    @classmethod
    def load_hardcoded_community(cls):
        # ensure that the community has not already been loaded (as a HardKilledCommunity)
        if not Dispersy.get_instance().has_community(cls.hardcoded_cid):
            return cls.load_community(Member.get_instance(cls.hardcoded_master_public_key))

    def __init__(self, master):
        super(SimpleDispersyTestCommunity, self).__init__(master)
        if __debug__: dprint(self._master_member.mid.encode("HEX"))

        # ensure that two of the hardcoder members (A, B, or C) has been picked
        cluster = self.get_meta_message(u"last-1-subjective-sync").destination.cluster
        subjective_set = self.get_subjective_set(self._my_member, cluster)
        assert subjective_set
        assert self._my_member.public_key in subjective_set
        def count():
            counter = 0
            for name, public_key in self.hardcoded_member_public_keys.iteritems():
                if public_key in subjective_set:
                    if __debug__: dprint("hardcoded member ", name, " found in my subjective set")
                    counter += 1
            return counter
        # if (1) we are not one of the hardcoded members and (2) we did not yet pick hardcoded
        # members for our subjective set
        if not self._my_member.public_key in self.hardcoded_member_public_keys.values() and count() < 2:
            assert count() == 0
            assert len(self.hardcoded_member_public_keys) == 3
            keys = self.hardcoded_member_public_keys.values()
            shuffle(keys)
            self.create_dispersy_subjective_set(cluster, [self._my_member, self.get_member(keys[0]), self.get_member(keys[1])])
            subjective_set = self.get_subjective_set(self._my_member, cluster)
            assert count() == 2

        self._status = get_status_holder("dispersy-simple-dispersy-test")
        self._status.add_reporter(TUDelftReporter(REPORTER_NAME, 300, self._my_member.public_key))
        self._status.create_and_add_event("__init__^" + self._master_member.mid.encode("HEX"), ["last-1-subjective-sync"])
        self._status.create_and_add_event("info^" + self._master_member.mid.encode("HEX"), [self._dispersy.info()])
        self._status.create_and_add_event("subjective_set^" + self._master_member.mid.encode("HEX"), [(name, public_key in subjective_set) for name, public_key in self.hardcoded_member_public_keys.iteritems()])
        self._status.report_now()
        self._dispersy.callback.register(self._periodically_info, delay=60.0)

    def initiate_meta_messages(self):
        return [Message(self, u"last-1-subjective-sync", MemberAuthentication(encoding="sha1"), LinearResolution(), LastSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=129, history_size=1), SubjectiveDestination(cluster=1, node_count=1), TextPayload(), self.check_last_1_subjective_sync, self.on_last_1_subjective_sync, delay=5.0)]

    def initiate_conversions(self):
        return [DefaultConversion(self), Conversion(self)]

    def dispersy_cleanup_community(self, message):
        if __debug__: dprint(self._master_member.mid.encode("HEX"))
        self._status.create_and_add_event("dispersy_cleanup_community^" + self._master_member.mid.encode("HEX") , [("is_soft_kill", message.payload.is_soft_kill), ("is_hard_kill", message.payload.is_hard_kill)])
        self._status.report_now()
        self._status.get_reporter(REPORTER_NAME).stop()
        self._status.remove_reporter(REPORTER_NAME)
        self._status.add_reporter(NullReporter("Periodically remove all events", 60))

        # will reclassify to SoftKilledCommunity or HardKilledCommunity
        return super(SimpleDispersyTestCommunity, self).dispersy_cleanup_community(message)

    def on_last_1_subjective_sync(self, messages):
        if __debug__: dprint(self._master_member.mid.encode("HEX"))
        self._status.create_and_add_event("on_last_1_subjective_sync^" + self._master_member.mid.encode("HEX"), [(message.address, message.distribution.global_time, message.payload.text) for message in messages])

    def create_last_1_subjective_sync(self, text):
        if __debug__: dprint(self._master_member.mid.encode("HEX"))
        assert isinstance(text, unicode)
        meta = self.get_meta_message(u"last-1-subjective-sync")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(True,),
                            payload=(text,))
        self._dispersy.store_update_forward([message], True, True, True)
        return message

    def check_last_1_subjective_sync(self, messages):
        if __debug__: dprint(self._master_member.mid.encode("HEX"))
        for message in messages:
            allowed, proofs = self._timeline.check(message)
            if allowed:
                yield message
            else:
                yield DelayMessageByProof(message)

    def on_last_1_subjective_sync(self, messages):
        if __debug__: dprint(self._master_member.mid.encode("HEX"))
        self._status.create_and_add_event("on_last_1_subjective_sync^" + self._master_member.mid.encode("HEX"), [(message.address, message.distribution.global_time, message.payload.text) for message in messages])

    def _periodically_info(self):
        while True:
            self._status.create_and_add_event("info^" + self._master_member.mid.encode("HEX"), [self._dispersy.info(attributes=False)])
            yield 60.0

