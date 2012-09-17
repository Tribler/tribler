"""
Usage:
python -O -c "from Tribler.dispersy.tool.main import main; main()" --statedir STATEDIR --script Tribler.community.effort.script.CrawlerScript | multilog t n1024 s104857600 STATEDIR
"""

from Tribler.community.effort.community import EffortCommunity
from Tribler.dispersy.community import HardKilledCommunity
from Tribler.dispersy.dprint import dprint
from Tribler.dispersy.member import Member
from Tribler.dispersy.revision import update_revision_information
from Tribler.dispersy.script import ScriptBase
from Tribler.dispersy.tool.scenarioscript import ScenarioScript
from dispersy.tool.lencoder import bz2log

# update version information directly from SVN
update_revision_information("$HeadURL$", "$Revision$")

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
            private_key = open("effort_master_private_key.bin", "r").read()
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
        return "3081a7301006072a8648ce3d020106052b810400270381920004039bb20a07b2c09fe2eb0d75a6ab8f23503728fb105c5b34fea181d2b30130fa5b493ee6317b5af3b079d3509a0225d8bafd940438e07aa48b76a37ace874a1612cbcd0878f8b7eb03b95d6bb27992d61a165a657c2b1fe096e2d39998fca7604f3bf3cf317c33be8e449c5015fbef8981f6f9d5d4ddc38f2c728cf823f9faca3224629ab6282b29136117b21737c0f4".decode("HEX")

    @property
    def community_class(self):
        return EffortCommunity

    def log(self, _message, **kargs):
        bz2log("log", _message, **kargs)
