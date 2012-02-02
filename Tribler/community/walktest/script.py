"""
Example file

python Tribler/Main/dispersy.py --script walktest-scenario
"""

import time

from community import WalktestCommunity

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.script import ScriptBase

class ScenarioScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))
        self._community = None

        self.caller(self.scenario)

    def yield_events(self):
        """
        Yields (TIMESTAMP, METHOD, ARGS) tuples, where TIMESTAMP is the time when METHOD must be called.
        """
        # beginstamp = int(self._kargs["beginstamp"])
        endstamp = int(self._kargs["endstamp"])

        yield endstamp, self.on_end, ()

    def get_or_create_community(self):
        if self._community is None:
            master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004008be5c9f62d949787a3470e3ed610c30eab479ae3f4e97af987ea2c25f68a23ff3754d0e59f22839444479e6d0e4db9e8e46752d067b0764388a6a174511950fb66655a65f819fc065de7c383477a1c2fecdad0d18e529b1ae003a4c6c7abf899bd301da7689dd76ce248042477c441be06e236879af834f1def7c7d9848d34711bf1d1436acf00239f1652ecc7d1cb".decode("HEX")
            if False:
                # when crypto.py is disabled a public key is slightly
                # different...
                master_public_key = ";".join(("60", master_public_key[:60].encode("HEX"), ""))
            master = Member.get_instance(master_public_key)

            self._community = WalktestCommunity.join_community(master, self._my_member)
        return self._community

    def on_end(self):
        # last task
        pass

    def scenario(self):
        for deadline, call, args in self.yield_events():
            while True:
                remaining = deadline - time.time()
                if remaining > 0.1:
                    yield min(10.0, remaining)

                else:
                    call(*args)
                    break
