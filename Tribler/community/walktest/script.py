"""
Example file

python Tribler/Main/dispersy.py --script walktest-scenario
"""

try:
    from scipy.stats import poisson
except ImportError:
    pass

from random import random
from re import compile
import time

from community import WalktestCommunity

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.script import ScriptBase

class ScenarioScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))
        self._community = None

        self.caller(self.scenario)

    def get_scenario(self):
        """
        Yields (TIMESTAMP, METHOD, ARGS) tuples, where TIMESTAMP is the time when METHOD must be called.
        """
        re_line = compile("^([@+])\s*(?:(\d+):)?(\d+)(?:[.](\d+))?(?:\s*-\s*(?:(\d+):)?(\d+)(?:[.](\d+))?)?\s+(\w+)(?:\s+(.+?))?\s*$")
        filename = self._kargs["scenario"]
        origin = {"@":int(self._kargs["startstamp"]),
                  "+":time.time()}
        scenario = []
        for line in open(filename, "r"):
            match = re_line.match(line)
            if match:
                type_, bhour, bminute, bsecond, ehour, eminute, esecond, method, args = match.groups()
                begin = (int(bhour) * 3600.0 if bhour else 0.0) + (int(bminute) * 60.0) + (int(bsecond) if bsecond else 0.0)
                end = ((int(ehour) * 3600.0 if ehour else 0.0) + (int(eminute) * 60.0) + (int(esecond) if esecond else 0.0)) if eminute else 0.0
                assert end == 0.0 or begin <= end, "when end time is given it must be at or after the start time"
                scenario.append((origin[type_] + begin + (random() * (end - begin) if end else 0.0),
                                 getattr(self, "scenario_" + method), 
                                 tuple(args.split()) if args else ()))

        assert scenario, "scenario is empty"
        assert any(func.__name__ == "scenario_end" for _, func, _ in scenario), "scenario end is not defined"
        assert any(func.__name__ == "scenario_start" for _, func, _ in scenario), "scenario start is not defined"
        scenario.sort()

        # for deadline, method, args in scenario:
        #     dprint("scenario: @", deadline - startstamp, "s ", method, force=True)

        return scenario

    def get_or_create_community(self):
        return self._community

    def scenario_start(self):
        assert self._community is None
        master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004008be5c9f62d949787a3470e3ed610c30eab479ae3f4e97af987ea2c25f68a23ff3754d0e59f22839444479e6d0e4db9e8e46752d067b0764388a6a174511950fb66655a65f819fc065de7c383477a1c2fecdad0d18e529b1ae003a4c6c7abf899bd301da7689dd76ce248042477c441be06e236879af834f1def7c7d9848d34711bf1d1436acf00239f1652ecc7d1cb".decode("HEX")
        if False:
            # when crypto.py is disabled a public key is slightly
            # different...
            master_public_key = ";".join(("60", master_public_key[:60].encode("HEX"), ""))
        self._master_member = Member.get_instance(master_public_key)
        self._community = WalktestCommunity.join_community(self._master_member, self._my_member)
        self._community.auto_load = False

    def scenario_end(self):
        WalktestCommunity.scenario_end()
        return "END"

    def scenario_print(self, *args):
        dprint(*args, glue=" ", force=True)

    def _poisson_churn(self):
        while True:
            session_time = poisson.rvs(self._churn_mu)
            if self._community is None:
                dprint("poisson wants us online for the next ", session_time, " seconds")
                self._community = WalktestCommunity.load_community(self._master_member)
            else:
                dprint("poisson wants us online for the next ", session_time, " seconds (we are already online)")

            yield float(session_time)

            if self._community is None:
                dprint("poisson wants us offline (we are already offline, waiting 300 seconds anyway")
            else:
                dprint("poisson wants us offline (waiting 120 seconds)")
                self._community.unload_community()
                self._community = None
                yield 120.0

    def scenario_churn(self, mu):
        self._churn_mu = mu
        self._dispersy.callback.persistent_register("walktest-churn-identifier", self._poisson_churn)

    def scenario_churn_set(self, mu):
        self._churn_mu = mu

    def scenario_churn_online(self, chance):
        if self._community is None:
            chance = float(chance) / 100.0
            if random() < chance:
                dprint("going back online")
                self._community = WalktestCommunity.load_community(self._master_member)

    def scenario_churn_offline(self, chance):
        if not self._community is None:
            assert not self._community.auto_load
            chance = float(chance) / 100.0
            if random() < chance:
                dprint("going offline (", chance, ")")
                self._community.unload_community()
                self._community = None

    def scenario(self):
        for deadline, call, args in self.get_scenario():
            while True:
                remaining = deadline - time.time()
                if remaining > 0.1:
                    yield min(10.0, remaining)

                else:
                    if call(*args) == "END":
                        return
                    break
