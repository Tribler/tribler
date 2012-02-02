"""
Example file

python Tribler/Main/dispersy.py --script walktest-scenario
"""

import time
import itertools
import sys

from community import WalktestCommunity

from Tribler.Core.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.Core.dispersy.debug import Node
from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.member import Member
from Tribler.Core.dispersy.script import ScriptBase

from ldecoder import parse

class DebugNode(Node):
    def create_introduction_request(self, destination, source_internal, advice, identifier, global_time):
        meta = self._community.get_meta_message(u"introduction-request")
        return meta.impl(destination=(destination,), distribution=(global_time,), payload=(destination, source_internal, advice, identifier,))

class ScenarioScript(ScriptBase):
    def run(self):
        ec = ec_generate_key(u"low")
        self._my_member = Member.get_instance(ec_to_public_bin(ec), ec_to_private_bin(ec))

        self.caller(self.walk)

    def walk(self):
        master_public_key = "3081a7301006072a8648ce3d020106052b810400270381920004008be5c9f62d949787a3470e3ed610c30eab479ae3f4e97af987ea2c25f68a23ff3754d0e59f22839444479e6d0e4db9e8e46752d067b0764388a6a174511950fb66655a65f819fc065de7c383477a1c2fecdad0d18e529b1ae003a4c6c7abf899bd301da7689dd76ce248042477c441be06e236879af834f1def7c7d9848d34711bf1d1436acf00239f1652ecc7d1cb".decode("HEX")
        if False:
            # when crypto.py is disabled a public key is slightly
            # different...
            master_public_key = ";".join(("60", master_public_key[:60].encode("HEX"), ""))
        master = Member.get_instance(master_public_key)

        community = WalktestCommunity.join_community(master, self._my_member)
        # community._bootstrap_addresses = [("130.161.211.245", 6422)]
        # community.start_walk()

        # runtime
        if "endstamp" in self._kargs:
            while True:
                remaining = max(0.0, float(self._kargs["endstamp"]) - time.time())
                if remaining:
                    yield min(10.0, max(1.0, remaining))
                else:
                    break
        else:
            while True:
                yield 60.0

def main(filename):
    def ignore(lineno, datetime, message, **kargs):
        # if not message in ["logger"]:
        #     print "ignore", message, kargs.keys()

        if "candidates" in kargs:
            check_candidates(datetime, kargs["candidates"])

        if "lan_address" in kargs and "wan_address" in kargs:
            check_my_addresses(datetime, kargs["lan_address"], kargs["wan_address"])

    def check_my_addresses(datetime, lan_address, wan_address):
        if not public_addresses:
            public_addresses.append((datetime, lan_address, wan_address))

        elif not public_addresses[-1][1] == lan_address or not public_addresses[-1][2] == wan_address:
            public_addresses.append((datetime, lan_address, wan_address))

    def check_candidates(datetime, candidates):
        def to_string(candidate):
            if candidate[0] == candidate[1]:
                return "%s:%d" % candidate[0]
            else:
                return "%s:%d (%s:%d)" % (candidate[1][0], candidate[1][1], candidate[0][0], candidate[0][1])

        now_online = set(to_string(candidate) for candidate in candidates)
        if not now_online == current_online:
            online.append((datetime, now_online))

            current_online.clear()
            current_online.update(now_online)

        all_addresses.update(now_online)

    # def create_introduction_request(lineno, datetime, message, introduction_request, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     outgoing["introduction-request"] += 1

    #     key = "%s:%d" % introduction_request
    #     if key in out_intro_req:
    #         out_intro_req[key] += 1
    #     else:
    #         out_intro_req[key] = 1

    # def introduction_response_timeout(lineno, datetime, message, intermediary, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)

    #     key = "%s:%d" % intermediary
    #     if key in in_intro_timeout:
    #         in_intro_timeout[key] += 1
    #     else:
    #         in_intro_timeout[key] = 1

    # def introduction_response(lineno, datetime, message, source, introduction_address, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     incoming["introduction-response"] += 1
    #     all_addresses.add(source)

    #     key = " -> ".join(("%s:%d"%source, "%s:%d"%introduction_address))
    #     if key in in_intro_res:
    #         in_intro_res[key] += 1
    #     else:
    #         in_intro_res[key] = 1

    # def on_puncture_request(lineno, datetime, message, source, puncture, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     incoming["puncture-request"] += 1
    #     outgoing["puncture"] += 1
    #     all_addresses.add(source)

    # def on_puncture(lineno, datetime, message, source, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     incoming["puncture"] += 1
    #     all_addresses.add(source)

    # def on_introduction_request(lineno, datetime, message, source, introduction_response, puncture_request, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     incoming["introduction-request"] += 1
    #     outgoing["introduction-response"] += 1
    #     outgoing["puncture-request"] += 1
    #     all_addresses.add(source)

    # def on_introduction_response(lineno, datetime, message, source, candidates, public_address):
    #     check_public_address(datetime, public_address)
    #     check_candidates(datetime, candidates)
    #     incoming["introduction-response-unused"] += 1
    #     all_addresses.add(source)

    def init(lineno, datetime, message, candidates):
        assert len(candidates) == 0
        online.insert(0, (datetime, set()))

    def in_introduction_request(lineno, datetime, message, member, source, destination_address, source_lan_address, source_wan_address, advice, identifier):
        all_addresses.add(source)
        all_members.add(member)
        incoming["introduction-request"] += 1
        if advice:
            incoming["introduction-request-with-advice"] += 1

    def out_introduction_request(lineno, datetime, message, destination_address, source_lan_address, source_wan_address, advice, identifier):
        outgoing["introduction-request"] += 1
        if advice:
            outgoing["introduction-request-with-advice"] += 1

        key = "%s:%d" % destination_address
        if key in out_intro_req:
            out_intro_req[key] += 1
        else:
            out_intro_req[key] = 1

        walk.append(("request", key))

    def in_introduction_response(lineno, datetime, message, member, source, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, identifier):
        all_addresses.add(source)
        all_members.add(member)
        incoming["introduction-response"] += 1

        key = " -> ".join(("%s:%d"%source, "%s:%d"%wan_introduction_address))
        if key in in_intro_res:
            in_intro_res[key] += 1
        else:
            in_intro_res[key] = 1

        walk.append(("response", key))

    def out_introduction_response(lineno, datetime, message, destination_address, source_lan_address, source_wan_address, lan_introduction_address, wan_introduction_address, identifier):
        outgoing["introduction-response"] += 1

    def in_puncture_request(lineno, datetime, message, source, lan_walker_address, wan_walker_address):
        incoming["puncture-request"] += 1

    def out_puncture_request(lineno, datetime, message, destination, lan_walker_address, wan_walker_address):
        outgoing["puncture-request"] += 1

    def in_puncture(lineno, datetime, message, member, source):
        incoming["puncture"] += 1

    def out_puncture(lineno, datetime, message, destination):
        outgoing["puncture"] += 1

    def introduction_response_timeout(lineno, datetime, message, intermediary, advice):
        key = "%s:%d" % intermediary
        if key in in_intro_timeout:
            in_intro_timeout[key] += 1
        else:
            in_intro_timeout[key] = 1

    # public address
    public_addresses = []

    # churn
    online = []
    current_online = set()
    all_addresses = set()
    all_members = set()

    # walk
    walk = []
    out_intro_req = {}
    in_intro_res = {}
    in_intro_timeout = {}

    # counters
    # messages = {"introduction-request":52, "introduction-request-with-advice":52, "introduction-response":63, "puncture-request":43, "puncture":31}
    messages = {"introduction-request":1432, "introduction-request-with-advice":1432, "introduction-response":136, "puncture-request":37, "puncture":117}
    incoming = dict((key, 0) for key in messages)
    outgoing = dict((key, 0) for key in messages)

    mapping = {"__init__":init,
               "in-introduction-request":in_introduction_request,
               "in-introduction-response":in_introduction_response,
               "in-puncture-request":in_puncture_request,
               "in-puncture":in_puncture,
               "out-introduction-response":out_introduction_response,
               "out-introduction-request":out_introduction_request,
               "out-puncture-request":out_puncture_request,
               "out-puncture":out_puncture,
               "introduction-response-timeout":introduction_response_timeout,
               }

    first_datetime = None
    for lineno, datetime, message, kargs in parse(filename):
        if first_datetime is None:
            first_datetime = datetime
        last_datetime = datetime
        try:
            mapping.get(message, ignore)(lineno, datetime, message, **kargs)
        except Exception, exception:
            print "#", exception

    duration = last_datetime - first_datetime
    assert duration.days == 0
    seconds = duration.seconds

    # public addresses
    if public_addresses and online:
        last_datetime = public_addresses[0][0]
        for datetime, lan_address, wan_address in public_addresses:
            print datetime - first_datetime, " ", datetime - last_datetime, "  lan %s:%d" % lan_address, " wan %s:%d" % wan_address
        print

    # walk
    print "outgoing introduction request"
    total = sum(out_intro_req.itervalues())
    for count, key in sorted((count, key) for key, count in out_intro_req.iteritems()):
        print "%4d %22s" % (count, key), "=" * (250 * count / total)
    print

    last_type = ""
    last_key = ""
    for type_, key in walk:
        if last_type == "request" and type_ == "request":
            print last_key, "->", "timeout"

        if type_ == "response":
            if key.startswith(last_key):
                print key
            else:
                print "???", last_key, "->", key

        last_type, last_key = type_, key

    # performed walk summary
    print "walk-sum:", " ".join(key for type_, key in walk if type_ == "request")

    # for count, key in sorted((count, key) for key, count in in_intro_res.iteritems()):
    #     print "incoming introduction response", "%4d" % count, key
    # print

    # if not in_intro_timeout:
    #     print "no timeouts"
    # else:
    #     for count, key in sorted((count, key) for key, count in in_intro_timeout.iteritems()):
    #         print "incoming introduction timeout", "%4d" % count, key
    #     print sum(in_intro_timeout.itervalues()), "timeouts /", outgoing["introduction-request"], "requests"
    #     print

    # churn
    print "time      diff      count    discovered                 lost"
    if not online:
        print "-none-"
    else:
        last_datetime, last_candidates = online[0]
        for datetime, candidates in online:
            more = candidates.difference(last_candidates)
            less = last_candidates.difference(candidates)

            for candidate in more:
                print datetime - first_datetime, " ", datetime - last_datetime, "  %-5d" % len(candidates), " +", candidate
            for candidate in less:
                print datetime - first_datetime, " ", datetime - last_datetime, "  %-5d" % len(candidates), "                            -", candidate

            last_datetime, last_candidates = datetime, candidates
        print

    print "duration", duration, "->", seconds, "seconds"
    print "inverval", outgoing["introduction-request"], "requests -> ", 1.0 * seconds / outgoing["introduction-request"], "r/s"
    print len(all_addresses), len(all_members), "distinct addresses and members"
    print

    # counters
    factor, total_in, total_out = 1.0 / 1024 / 1024, 0, 0
    print "   in mbytes    b/s     out mbytes    b/s     diff    msg"
    for key, incoming, outgoing in [(key, incoming[key], outgoing[key]) for key in incoming.iterkeys()]:
        size_in = incoming * messages[key]
        speed_in = 1.0 * size_in / seconds
        total_in += size_in
        size_out = outgoing * messages[key]
        speed_out = 1.0 * size_out / seconds
        total_out += size_out
        print "%5d %6.3f %6.1f" % (incoming, size_in * factor, speed_in), \
            "  %5d %6.3f %6.1f" % (outgoing, size_out * factor, speed_out), \
            "  %5d" % abs(incoming - outgoing), \
            "   ", key
    print "===   %6.3f %6.1f" % (total_in * factor, 1.0 * total_in / seconds), \
        "        %6.3f %6.1f" % (total_out * factor, 1.0 * total_out / seconds)
    print

if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) == 2 else "walktest.log"
    main(filename)
