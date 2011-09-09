"""
Example file

python Tribler/Main/dispersy.py --script simpledispersytest-generate-messages
"""

from community import WalktestCommunity

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.script import ScriptBase

class DebugNode(Node):
    def create_introduction_request(self, destination, global_time):
        meta = self._community.get_meta_message(u"introduction-request")
        return meta.impl(destination=(destination,), distribution=(global_time,))

class ScenarioScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))

        # self.caller(self.t1)
        # self.caller(self.t2)
        self.caller(self.walk)

    def t1(self):
        # create community
        community = WalktestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)

        global_time = 10
        message = node.give_message(node.create_introduction_request(address, global_time), cache=True)
        yield community.get_meta_message(u"introduction-request").delay
        yield 1.0

        dprint("cleanup")
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def t2(self):
        # create community
        community = WalktestCommunity.create_community(self._my_member)
        address = self._dispersy.socket.get_address()

        # create node
        node = DebugNode()
        node.init_socket()
        node.set_community(community)
        node.init_my_member(candidate=False)

        global_time = 10
        message = node.give_message(node.create_introduction_request(address, global_time), cache=True)
        yield community.get_meta_message(u"introduction-request").delay
        yield 1.0

        community.start_walk()
        yield 20.0

        dprint("cleanup")
        community.create_dispersy_destroy_community(u"hard-kill")
        community.unload_community()

    def walk(self):
        master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004008be5c9f62d949787a3470e3ed610c30eab479ae3f4e97af987ea2c25f68a23ff3754d0e59f22839444479e6d0e4db9e8e46752d067b0764388a6a174511950fb66655a65f819fc065de7c383477a1c2fecdad0d18e529b1ae003a4c6c7abf899bd301da7689dd76ce248042477c441be06e236879af834f1def7c7d9848d34711bf1d1436acf00239f1652ecc7d1cb".decode("HEX")
        master = Member.get_instance(master_public_key)

        community = WalktestCommunity.join_community(master, self._my_member)
        community._bootstrap_addresses = [("127.0.0.1", 123)]
        community.start_walk()

        total = 60 * 60 * 5
        for i in xrange(total):
            dprint(total - i)
            yield 1.0
