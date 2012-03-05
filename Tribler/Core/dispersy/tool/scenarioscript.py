try:
    from scipy.stats import poisson, expon
except ImportError:
    poisson = expont = None
    print "Unable to import scipy.  ScenarioPoisson and ScenarioExpon are disabled"

from random import random
from re import compile as re_compile
from time import time

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.script import ScriptBase

class ScenarioScript(ScriptBase):
    def __init__(self, *args, **kargs):
        super(ScenarioScript, self).__init__(*args, **kargs)
        self._master_member = None
        self._community = None

    def run(self):
        self.caller(self._run_scenario)

    def _run_scenario(self):
        for deadline, _, call, args in self.parse_scenario():
            while True:
                remaining = deadline - time()
                if remaining > 0.1:
                    yield min(10.0, remaining)

                else:
                    if __debug__: dprint(call.__name__)
                    if call(*args) == "END":
                        return
                    break

    @property
    def my_member_security(self):
        return u"low"

    @property
    def master_member_public_key(self):
        raise NotImplementedError("must return an experiment specific master member public key")
            # if False:
            #     # when crypto.py is disabled a public key is slightly
            #     # different...
            #     master_public_key = ";".join(("60", master_public_key[:60].encode("HEX"), ""))
        # return "3081a7301006072a8648ce3d020106052b81040027038192000404668ed626c6d6bf4a280cf4824c8cd31fe4c7c46767afb127129abfccdf8be3c38d4b1cb8792f66ccb603bfed395e908786049cb64bacab198ef07d49358da490fbc41f43ade33e05c9991a1bb7ef122cda5359d908514b3c935fe17a3679b6626161ca8d8d934d372dec23cc30ff576bfcd9c292f188af4142594ccc5f6376e2986e1521dc874819f7bcb7ae3ce400".decode("HEX")

    @property
    def community_class(self):
        raise NotImplementedError("must return an experiment community class")

    @property
    def community_args(self):
        return ()

    @property
    def community_kargs(self):
        return {}

    def parse_scenario(self):
        """
        Yields (TIMESTAMP, FUNC, ARGS) tuples, where TIMESTAMP is the time when FUNC must be called.
        """
        re_line = re_compile("^([@+])\s*(?:(\d+):)?(\d+)(?:[.](\d+))?(?:\s*-\s*(?:(\d+):)?(\d+)(?:[.](\d+))?)?\s+(\w+)(?:\s+(.+?))?\s*$")
        filename = self._kargs["scenario"]
        origin = {"@":int(self._kargs["startstamp"]),
                  "+":time()}
        scenario = []
        for lineno, line in enumerate(open(filename, "r")):
            match = re_line.match(line)
            if match:
                type_, bhour, bminute, bsecond, ehour, eminute, esecond, func, args = match.groups()
                begin = (int(bhour) * 3600.0 if bhour else 0.0) + (int(bminute) * 60.0) + (int(bsecond) if bsecond else 0.0)
                end = ((int(ehour) * 3600.0 if ehour else 0.0) + (int(eminute) * 60.0) + (int(esecond) if esecond else 0.0)) if eminute else 0.0
                assert end == 0.0 or begin <= end, "when end time is given it must be at or after the start time"
                scenario.append((origin[type_] + begin + (random() * (end - begin) if end else 0.0),
                                 lineno,
                                 getattr(self, "scenario_" + func),
                                 tuple(args.split()) if args else ()))

        assert scenario, "scenario is empty"
        assert any(func.__name__ == "scenario_end" for _, _, func, _ in scenario), "scenario end is not defined"
        assert any(func.__name__ == "scenario_start" for _, _, func, _ in scenario), "scenario start is not defined"
        scenario.sort()

        if __debug__:
            for deadline, _, func, args in scenario:
                dprint("scenario: @", int(deadline - origin["@"]), "s ", func.__name__)

        return scenario

    def scenario_start(self):
        assert self._community is None
        ec = ec_generate_key(self.my_member_security)
        my_member = Member(ec_to_public_bin(ec), ec_to_private_bin(ec))
        self._master_member = Member(self.master_member_public_key)
        dprint("join community ", self._master_member.mid.encode("HEX"), " as ", my_member.mid.encode("HEX"))
        self._community = self.community_class.join_community(self._master_member, my_member, *self.community_args, **self.community_kargs)
        self._community.auto_load = False

    def scenario_end(self):
        dprint("END")
        return "END"

    def scenario_print(self, *args):
        dprint(*args, glue=" ", force=True)

if poisson:
    class ScenarioPoisson(object):
        def __poisson_churn(self):
            while True:
                delay = poisson.rvs(self.__poisson_online_mu)
                if self._community is None:
                    dprint("poisson wants us online for the next ", delay, " seconds")
                    self._community = self.community_class.load_community(self._master_member, *self.community_args, **self.community_kargs)
                else:
                    dprint("poisson wants us online for the next ", delay, " seconds (we are already online)")
                yield float(delay)

                delay = poisson.rvs(self.__poisson_offline_mu)
                if self._community is None:
                    dprint("poisson wants us offline for the next ", delay, " seconds (we are already offline)")
                else:
                    dprint("poisson wants us offline for the next ", delay, " seconds")
                    self._community.unload_community()
                    self._community = None
                yield float(delay)

        def scenario_poisson_churn(self, online_mu, offline_mu):
            self.__poisson_online_mu = online_mu
            self.__poisson_offline_mu = offline_mu
            self._dispersy.callback.persistent_register("scenario-poisson-identifier", self.__poisson_churn)

if expon:
    class ScenarioExpon(object):
        def __expon_churn(self):
            while True:
                delay = expon.rvs(self.__expon_online_beta)
                if delay:
                    delay = max(60.0, delay)
                    if self._community is None:
                        dprint("expon wants us online for the next ", delay, " seconds")
                        self._community = self.community_class.load_community(self._master_member, *self.community_args, **self.community_kargs)
                    else:
                        dprint("expon wants us online for the next ", delay, " seconds (we are already online)")
                    yield float(delay)

                delay = expon.rvs(self.__expon_offline_beta)
                if delay:
                    delay = max(60.0, delay)
                    if self._community is None:
                        dprint("expon wants us offline for the next ", delay, " seconds (we are already offline)")
                    else:
                        dprint("expon wants us offline for the next ", delay, " seconds")
                        self._community.unload_community()
                        self._community = None
                    yield float(delay)

        def scenario_expon_churn(self, online_beta, offline_beta):
            self.__expon_online_beta = online_beta
            self.__expon_offline_beta = offline_beta
            self._dispersy.callback.persistent_register("scenario-expon-identifier", self.__expon_churn)

class ScenarioChurn(object):
    def scenario_online(self, chance):
        if self._community is None:
            chance = float(chance) / 100.0
            if random() < chance:
                dprint("going back online")
                self._community = self.community_class.load_community(self._master_member, *self.community_args, **self.community_kargs)

    def scenario_offline(self, chance):
        if not self._community is None:
            assert not self._community.auto_load
            chance = float(chance) / 100.0
            if random() < chance:
                dprint("going offline (", chance, ")")
                self._community.unload_community()
                self._community = None
