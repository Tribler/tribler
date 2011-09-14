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

from ldecoder import parse

class DebugNode(Node):
    def create_introduction_request(self, destination, global_time):
        meta = self._community.get_meta_message(u"introduction-request")
        return meta.impl(destination=(destination,), distribution=(global_time,), payload=(destination,))

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
        if True:
            # when crypto.py is disabled a public key is slightly
            # different...
            master_public_key = ";".join(("60", master_public_key[:60].encode("HEX"), ""))
        master = Member.get_instance(master_public_key)

        community = WalktestCommunity.join_community(master, self._my_member)
        community._bootstrap_addresses = [("130.161.211.245", 6422)]
        community.start_walk()

        total = 60 * 60 * 5
        for i in xrange(total):
            dprint(total - i)
            yield 1.0

def main():
    def ignore(lineno, datetime, message, **kargs):
        if not message in ["logger"]:
            print "ignore", message, kargs.keys()

    def check_candidates(datetime, candidates):
        now_online = set("%s:%d" % candidate for candidate in candidates)
        if not now_online == current_online:
            online.append((datetime, now_online))

            current_online.clear()
            current_online.update(now_online)

    def create_introduction_request(lineno, datetime, message, introduction_request, candidates):
        check_candidates(datetime, candidates)
        outgoing["introduction-request"] += 1

        key = "%s:%d" % introduction_request
        if key in out_intro_req:
            out_intro_req[key] += 1
        else:
            out_intro_req[key] = 1

    def introduction_response_timeout(lineno, datetime, message, candidates):
        check_candidates(datetime, candidates)

    def introduction_response(lineno, datetime, message, source, introduction_address, candidates):
        check_candidates(datetime, candidates)
        incoming["introduction-response"] += 1

        key = " -> ".join(("%s:%d"%source, "%s:%d"%introduction_address))
        if key in in_intro_res:
            in_intro_res[key] += 1
        else:
            in_intro_res[key] = 1

    def on_puncture_request(lineno, datetime, message, source, puncture, candidates):
        check_candidates(datetime, candidates)
        incoming["puncture-request"] += 1
        outgoing["puncture"] += 1

    def on_puncture(lineno, datetime, message, source, candidates):
        check_candidates(datetime, candidates)
        incoming["puncture"] += 1

    def on_introduction_request(lineno, datetime, message, source, introduction_response, puncture_request, candidates):
        check_candidates(datetime, candidates)
        incoming["introduction-request"] += 1
        outgoing["introduction-response"] += 1
        outgoing["puncture-request"] += 1

    def init(lineno, datetime, message, candidates):
        assert len(candidates) == 0
        online.insert(0, (datetime, set()))

    # churn
    online = []
    current_online = set()

    # walk
    out_intro_req = {}
    in_intro_res = {}

    # counters
    incoming = {"introduction-request":0, "introduction-response":0, "puncture-request":0, "puncture":0}
    outgoing = {"introduction-request":0, "introduction-response":0, "puncture-request":0, "puncture":0}

    mapping = {"create_introduction_request":create_introduction_request,
               "introduction_..._timeout":introduction_response_timeout,
               "introduction_response_...":introduction_response,
               "on_puncture":on_puncture,
               "on_introduction_request":on_introduction_request,
               "on_puncture_request":on_puncture_request,
               "__init__":init}
    for lineno, datetime, message, kargs in parse("walktest.log"):
        mapping.get(message, ignore)(lineno, datetime, message, **kargs)

    for count, key in sorted((count, key) for key, count in out_intro_req.iteritems()):
        print "outgoing introduction request", "%4d" % count, key
    print

    for count, key in sorted((count, key) for key, count in in_intro_res.iteritems()):
        print "incoming introduction response", "%4d" % count, key
    print

    print "in    out   diff  msg"
    for key, incoming, outgoing in [(key, incoming[key], outgoing[key]) for key in incoming.iterkeys()]:
        print "%-5d" % incoming, "%-5d" % outgoing, "%-5d" % abs(incoming - outgoing), key
    print

    print "diff     count    discovered                 lost"
    last_datetime, last_candidates = online[0]
    for datetime, candidates in online[1:]:
        more = candidates.difference(last_candidates)
        less = last_candidates.difference(candidates)

        for candidate in more:
            print datetime - last_datetime, " %-5d" % len(candidates), " +", candidate
        for candidate in less:
            print datetime - last_datetime, " %-5d" % len(candidates), "                            -", candidate

        last_datetime, last_candidates = datetime, candidates

if __name__ == "__main__":
    main()
