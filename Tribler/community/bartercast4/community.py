# Written by Cor-Paul Bezemer

from twisted.internet.defer import inlineCallbacks

from Tribler.community.basecommunity import BaseCommunity
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from .statistics import BartercastStatisticTypes, _barter_statistics
from twisted.internet.task import LoopingCall
from twisted.python import log

# TODO REMOVE BACKWARD COMPATIBILITY: Delete this import
from Tribler.community.bartercast4.compatibility import Bartercast4Compatibility, StatisticsConversion

BARTERCAST_PERSIST_INTERVAL = 120.0


class BarterCommunity(BaseCommunity):
    @classmethod
    def get_master_members(cls, dispersy):
# generated: Thu Oct 30 12:59:19 2014
# curve: NID_sect571r1
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000405ef988346197abe009065e6f9f517263063495554e4d278074feb1be3e81586b44f90b8a11f170f0a059d8f26c259118e6afc775f3d1e7c46462c9de0ec2bb94e480390622056b002c1f121acc52c18a0857ce59e79cf73642a4787fcdc5398d332000fbd44b16f14b005c0910d81cb85392fd036f32a242044c8263e0c6b9dc10b68f9c30540cfbd8a6bb5ccec786e
# pub-sha1 59accbc05521d8b894e8e6ef8d686411384cdec9
#-----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQF75iDRhl6vgCQZeb59RcmMGNJVVTk
# 0ngHT+sb4+gVhrRPkLihHxcPCgWdjybCWRGOavx3Xz0efEZGLJ3g7Cu5TkgDkGIg
# VrACwfEhrMUsGKCFfOWeec9zZCpHh/zcU5jTMgAPvUSxbxSwBcCRDYHLhTkv0Dbz
# KiQgRMgmPgxrncELaPnDBUDPvYprtczseG4=
#-----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000405ef988346197abe009065e6f9f517263063495554e4d278074feb1be3e81586b44f90b8a11f170f0a059d8f26c259118e6afc775f3d1e7c46462c9de0ec2bb94e480390622056b002c1f121acc52c18a0857ce59e79cf73642a4787fcdc5398d332000fbd44b16f14b005c0910d81cb85392fd036f32a242044c8263e0c6b9dc10b68f9c30540cfbd8a6bb5ccec786e".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def __init__(self, dispersy, master, my_member):
        super(BarterCommunity, self).__init__(dispersy, master, my_member)
        self._dispersy = dispersy
        log.msg("joined BC community")
        self.init_database()

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete the following 2 assignments
        self.compatibility = Bartercast4Compatibility(self)
        self.compatibility_mode = True

        # add task for persisting bartercast statistics every BARTERCAST_PERSIST_INTERVAL seconds
        self._logger.debug("bartercast persist task started")
        self.register_task("bartercast persist",
                           LoopingCall(self.backup_bartercast_statistics)).start(BARTERCAST_PERSIST_INTERVAL, now=False)

    def init_database(self):
        log.msg("loading BC statistics from database")
        _barter_statistics.load_statistics(self._dispersy)

    def initiate_meta_messages(self):
        self.register_traversal("StatsRequest",
                                MemberAuthentication(),
                                PublicResolution(),
                                DirectDistribution(),
                                CandidateDestination())
        self.register_traversal("StatsResponse",
                                MemberAuthentication(),
                                PublicResolution(),
                                DirectDistribution(),
                                CandidateDestination())

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete deprecated call
        return (super(BarterCommunity, self).initiate_meta_messages() +
                self.compatibility.deprecated_meta_messages())

    def initialize(self, integrate_with_tribler=False, auto_join_channel=False):
        super(BarterCommunity, self).initialize()

    def initiate_conversions(self):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method
        return [DefaultConversion(self), StatisticsConversion(self)]

    def on_basemsg(self, messages):
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete this method

        # Apparently the big switch is happening,
        # start talking newspeak:
        self.compatibility_mode = False
        super(BarterCommunity, self).on_basemsg(messages)

    def create_stats_request(self, candidate, stats_type):
        log.msg("Creating stats-request for type %d to member: %s" % (stats_type,
                                                                      candidate._association.mid.encode("hex")))
        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"stats-request")
            message = meta.impl(authentication=(self._my_member,),
                                distribution=(self.claim_global_time(),),
                                destination=(candidate,),
                                payload=(stats_type,))
            self._dispersy._forward([message])
        else:
            options = self.get_traversal("StatsRequest",
                                         auth=(self._my_member,),
                                         dist=(self.claim_global_time(),),
                                         dest=(candidate,))
            self.forward(options, "bartercast4.StatsRequest", stats_type)

    def check_statsrequest(self, header, message):
        allowed, _ = self._timeline.check(header)
        if allowed:
            yield header
        else:
            yield DelayMessageByProof(header)

    def on_statsrequest(self, header, message):
        log.msg("IN: stats-request")
        log.msg("stats-request: %s %s" % (header._distribution.global_time, message.statstype))
        # send back stats-response
        self.create_stats_response(message.statstype, header.candidate)

    def create_stats_response(self, stats_type, candidate):
        log.msg("OUT: stats-response")
        records = _barter_statistics.get_top_n_bartercast_statistics(stats_type, 5)
        log.msg("sending stats for type %d: %s" % (stats_type, records))

        # TODO REMOVE BACKWARD COMPATIBILITY: Delete if statement and positive case
        if self.compatibility_mode:
            meta = self.get_meta_message(u"stats-response")
            message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(candidate,),
                            payload=(stats_type, records))
            self._dispersy._forward([message])
        else:
            options = self.get_traversal("StatsResponse",
                                         auth=(self._my_member,),
                                         dist=(self.claim_global_time(),),
                                         dest=(candidate,))
            self.forward(options, "bartercast4.StatsResponse", stats_type, records)

    def check_statsresponse(self, header, message):
        allowed, _ = self._timeline.check(header)
        if allowed:
            yield header
        else:
            yield DelayMessageByProof(header)

    def on_statsresponse(self, header, message):
        log.msg("IN: stats-response")
        log.msg("stats-response: %s %s %s"
                % (header._distribution.global_time, message.statstype, message.records))
        for r in message.records:
            _barter_statistics.log_interaction(self._dispersy,
                                               message.statstype,
                                               "%s:%s" % (header.candidate.sock_addr[0],
                                                          header.candidate.sock_addr[1]),
                                               r.peerid,
                                               int(str(r.value).encode('hex'), 16))

    # bartercast accounting stuff
    def backup_bartercast_statistics(self):
        self._logger.debug("merging bartercast statistics")
        _barter_statistics.persist(self._dispersy)

    @inlineCallbacks
    def unload_community(self):
        self._logger.debug("unloading the Barter4 community")
        # store last cached statistics
        # this screws up for some reason so disable for now...
        # TODO we lose only a small part (max 2 minutes) of statistics but should be fixed
        # self.backup_bartercast_statistics()

        # close database
        _barter_statistics.close()
        yield super(BarterCommunity, self).unload_community()


class BarterCommunityCrawler(BarterCommunity):

    def __init__(self, *args, **kargs):
        super(BarterCommunityCrawler, self).__init__(*args, **kargs)

    def on_introduction_response(self, messages):
        super(BarterCommunity, self).on_introduction_response(messages)
        for message in messages:
            log.msg("in on_introduction_response: Requesting stats from %s" % message.candidate)
            for t in BartercastStatisticTypes.reverse_mapping:
                self.create_stats_request(message.candidate, t)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(1.0, now=True)
