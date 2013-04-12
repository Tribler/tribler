"""
Usage:
python -O -c "from Tribler.dispersy.tool.main import main; main()" --statedir STATEDIR --script Tribler.community.effort.script.CrawlerScript | multilog t n1024 s104857600 STATEDIR
"""

from Tribler.community.effort.community import EffortCommunity, MASTER_MEMBER_PUBLIC_KEY
from Tribler.dispersy.community import HardKilledCommunity
from Tribler.dispersy.dprint import dprint
from Tribler.dispersy.member import Member
from Tribler.dispersy.script import ScriptBase
from Tribler.dispersy.tool.scenarioscript import ScenarioScript
from Tribler.dispersy.tool.lencoder import bz2log

class CrawlerScript(ScriptBase):
    @property
    def enable_wait_for_wan_address(self):
        return False

    def run(self):
        self._community = None
        self.add_testcase(self.setup)
        self.add_testcase(self.crawl)

    def check_master_private_key(self):
        if not self._community.master_member.private_key:
            private_key = open("_" + self._community.cid.encode("HEX") + ".private_key", "r").read()
            Member(self._community.master_member.public_key, private_key)
            assert self._community.master_member.private_key == private_key

    def setup(self):
        """ Join or load the effort community """
        self._dispersy.define_auto_load(HardKilledCommunity)
        self._dispersy.define_auto_load(EffortCommunity)

        for master in EffortCommunity.get_master_members():
            if self._dispersy.has_community(master.mid):
                continue

            dprint("loading cid ", master.mid.encode("HEX"), force=True)
            self._community = EffortCommunity.load_community(master)
            dprint("using mid   ", self._community.my_member.mid.encode("HEX"), force=True)

            # try to find dispersy-identity for the master member
            if not master.has_identity(self._community):
                self.check_master_private_key()
                self._community.create_dispersy_identity(sign_with_master=True)

            # ensure that my_member is allowed to ask for the debug statistics
            allowed, _ = self._community.timeline.allowed(self._community.get_meta_message(u"debug-request"))
            if not allowed:
                self.check_master_private_key()
                self._community.create_dispersy_authorize([(self._community.my_member, self._community.get_meta_message(u"debug-request"), u"permit")], sign_with_master=True, forward=False)

    def crawl(self):
        """ Crawl the effort community until closed """
        while True:
            yield 60.0
            self._community.create_debug_request()


class DestroyCommunityScript(CrawlerScript):
    def run(self):
        self._community = None
        self.add_testcase(self.setup)
        self.add_testcase(self.destroy)

    def destroy(self):
        """ Destroy the effort community """
        self.check_master_private_key()

        for i in xrange(10, 0, -1):
            dprint("CID: ", self._community.cid.encode("HEX"), level="warning")
            dprint("WARNING: the community will be destroyed in ", i, " seconds!", level="warning")
            yield 1.0

        # DESTROY!
        self._community.create_dispersy_destroy_community(u"hard-kill", sign_with_master=True)

        for i in xrange(60):
            dprint("WARNING: leave running to improve message propagation", level="warning")
            yield 1.0

class TriblerEffortScript(ScenarioScript):
    """
    Runs a Tribler instance from console that joins the EffortCommunity to increase the overall
    workload.
    """
    @property
    def enable_wait_for_wan_address(self):
        return False

    @property
    def my_member_security(self):
        return u"NID_secp224r1"

    @property
    def master_member_public_key(self):
        return MASTER_MEMBER_PUBLIC_KEY

    @property
    def community_class(self):
        return EffortCommunity

    def log(self, _message, **kargs):
        bz2log("log", _message, **kargs)
