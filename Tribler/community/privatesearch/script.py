import sys
import os
from random import randint, shuffle
from collections import defaultdict
from traceback import print_exc
from time import sleep

from community import SearchCommunity, PSearchCommunity, HSearchCommunity, PoliSearchCommunity
from Tribler.community.privatesemantic.script import SemanticScript

from Tribler.dispersy.member import Member
from Tribler.dispersy.tool.lencoder import log

from threading import Thread
from Tribler.dispersy.script import ScenarioScriptBase
from Tribler.community.privatesearch.oneswarm.community import PoliOneSwarmCommunity

class SearchScript(SemanticScript):
    def __init__(self, **kargs):
        SemanticScript.__init__(self, **kargs)

        def parse_tuplestr(v):
            if len(v) > 1 and v[1] == "t":
                return (int(v[0]), int(v[2:]))
            if len(v) > 1 and v[1] == ".":
                return float(v)
            return int(v)

        def str2bool(v):
            return v.lower() in ("yes", "true", "t", "1")

        if self.community_type != "oneswarm":
            if 'ttl' in kargs:
                self.community_kargs['ttl'] = parse_tuplestr(kargs['ttl'])
            if 'neighbors' in kargs:
                self.community_kargs['neighbors'] = parse_tuplestr(kargs['neighbors'])
            if 'fneighbors' in kargs:
                self.community_kargs['fneighbors'] = parse_tuplestr(kargs['fneighbors'])
            if 'prob' in kargs:
                self.community_kargs['prob'] = float(kargs['prob'])
        else:
            if 'cancel_after' in kargs:
                self.community_kargs['cancel_after'] = parse_tuplestr(kargs['cancel_after'])

        self.community_kargs['use_megacache'] = str2bool(kargs.get('use_megacache', 'true'))

        self.do_search = int(kargs.get('dosearch', 1000))
        self.search_limit = int(kargs.get('search_limit', sys.maxint))
        self.search_spacing = float(kargs.get('search_spacing', 15.0))

        self.nr_search = 0
        self.file_availability = defaultdict(list)

    def join_community(self, my_member):
        self.my_member = my_member

        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404f10c33b03d2a09943d6d6a4b2cf4fe3129e5dce1df446a27d0ce00d48c845a4eff8102ef3becd6bc07c65953c824d227ebc110016d5ba71163bf6fb83fde7cdccf164bb007e27d07da952c47d30cf9c843034dc7a4603af3a84f8997e5d046e6a5f1ad489add6878898079a4663ade502829577c7d1e27302a3d5ea0ae06e83641a093a87465fdd4a3b43e031a9555".decode("HEX")
        master = Member(master_key)

        log(self._logfile, "joining community with kargs", kargs=self.community_kargs)

        if self.community_type == 'search':
            community = SearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches=True, **self.community_kargs)
        elif self.community_type == 'hsearch':
            community = HSearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches=True, **self.community_kargs)
        elif self.community_type == 'polisearch':
            community = PoliSearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches=True, **self.community_kargs)
        elif self.community_type == 'oneswarm':
            community = PoliOneSwarmCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches=True, **self.community_kargs)
        else:
            community = PSearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches=True, **self.community_kargs)

        self._add_taste_buddies = community.add_taste_buddies
        community.add_taste_buddies = self.log_taste_buddies

        self._manual_create_introduction_request = community.create_introduction_request
        if self.manual_connect:
            community.create_introduction_request = lambda destination, allow_sync: self._manual_create_introduction_request(destination, False)

        if int(self._my_name) <= self.late_join:
            self._create_introduction_request = community.create_introduction_request
            community.create_introduction_request = lambda *args: None

        self._dispersy.callback.register(self.monitor_taste_buddy, delay=1.0)
        def stop_dispersy():
            Thread(target=self._dispersy.stop, args=(10.0,)).start()
        # self._dispersy.callback.register(stop_dispersy, delay=300.0)

        # my_name is only available after _run method is called
        self.search_offset = 200 + (int(self._my_name) % int(self.search_spacing))

        # parse datasets of all other peers
        fp = open('data/file_availability.log')
        for line in fp:
            infohash, peers = line.strip().split()
            infohash = infohash + " "* (20 - len(infohash))

            peers = [peer for peer in map(int, peers.split(',')) if peer != int(self._my_name)]
            self.file_availability[infohash] = peers
        fp.close()

        return community

    def get_commands_from_fp(self, fp, step):
        search_step = step + self.search_offset
        perform_search = search_step % 300 == 0 and (self._community.ttl or self._community.forwarding_prob)
        if perform_search:
            nr_search = search_step / 300
            if nr_search <= self.search_limit and int(self._my_name) <= self.do_search:
                self.nr_search = nr_search
                self._dispersy.callback.persistent_register("do_search", self.perform_searches)

        return SemanticScript.get_commands_from_fp(self, fp, step)

    def log_statistics(self):
        while True:
            latejoin = taste_ratio = 0

            if len(self.taste_buddies):
                connected_taste_buddies = len(self.taste_buddies) - len(self.not_connected_taste_buddies)
                ratio = connected_taste_buddies / min(10.0, float(len(self.taste_buddies)))
                if int(self._my_name) <= self.late_join:
                    latejoin = ratio / float(self.late_join)
                else:
                    taste_ratio = ratio / float(self._nr_peers - self.late_join)

            recall = len(self.test_reply) / float(len(self.test_set))
            recall /= float(self.do_search)

            paths_found = sum(len(paths) for paths in self.test_reply.itervalues())
            sources_found = 0
            for infohash, peers in self.test_reply.iteritems():
                sources_found += sum(peer in self.file_availability[infohash] for peer in set(peers))

            unique_sources = float(sum([len(self.file_availability[infohash]) for infohash in self.test_reply.iterkeys()]))
            if unique_sources:
                sources_found = sources_found / unique_sources
                paths_found = paths_found / unique_sources

            paths_found /= float(self.do_search)
            sources_found /= float(self.do_search)

            log("dispersy.log", "scenario-statistics", bootstrapped=taste_ratio, latejoin=latejoin, recall=recall, nr_search_=self.nr_search, paths_found=paths_found, sources_found=sources_found)
            log("dispersy.log", "scenario-debug", not_connected=list(self.not_connected_taste_buddies), search_forward=self._community.search_forward, search_forward_success=self._community.search_forward_success, search_forward_timeout=self._community.search_forward_timeout, search_endpoint=self._community.search_endpoint, search_cycle_detected=self._community.search_cycle_detected, search_no_candidates_remain=self._community.search_no_candidates_remain, search_megacachesize=self._community.search_megacachesize, create_time_encryption=self._community.create_time_encryption, create_time_decryption=self._community.create_time_decryption, receive_time_encryption=self._community.receive_time_encryption, search_timeout=self._community.search_timeout, send_packet_size=self._community.send_packet_size, reply_packet_size=self._community.reply_packet_size, forward_packet_size=self._community.forward_packet_size)
            yield 5.0

    def log_search_response(self, keywords, results, candidate):
        for result in results:
            if result[0] in self.test_set:
                ip, port = result[1].split()
                peer = int(port[:-1]) - 12000
                self.test_reply[result[0]].append(peer)

                if peer not in self.file_availability[result[0]]:
                    print >> sys.stderr, "peer", peer, "does not have", result[0], self.file_availability[result[0]]

        recall = len(self.test_reply) / float(len(self.test_set))
        paths_found = sum(len(paths) for paths in self.test_reply.itervalues())
        sources_found = 0
        for infohash, peers in self.test_reply.iteritems():
            sources_found += sum(peer in self.file_availability[infohash] for peer in set(peers))

        unique_sources = float(sum([len(self.file_availability[infohash]) for infohash in self.test_reply.iterkeys()]))
        if unique_sources:
            sources_found = sources_found / unique_sources
            paths_found = paths_found / unique_sources

        if results:
            log(self._logfile, "results", recall=recall, paths_found=paths_found, sources_found=sources_found, keywords=keywords, candidate=str(candidate), results=results, unique_sources=unique_sources)
        else:
            log(self._logfile, "no results", recall=recall, paths_found=paths_found, sources_found=sources_found, keywords=keywords, candidate=str(candidate), unique_sources=unique_sources)

    def perform_searches(self):
        # clear local test_reply dict + force remove test_set from megacache
        self.test_reply.clear()
        for infohash in self.test_set:
            self._community._torrent_db.deleteTorrent(infohash)

        for infohash in self.test_set:
            candidates, local_results, identifier = self._community.create_search([unicode(infohash)], self.log_search_response)
            candidates = map(str, candidates)
            log(self._logfile, "send search query for '%s' with identifier %d to %d candidates" % (infohash, identifier, len(candidates)), candidates=candidates)

            if local_results:
                self.log_search_response([unicode(infohash)], local_results, None)

            yield self.search_spacing


def start_script():
    if not os.path.isdir('data'):
        os.mkdir('data')

    f = open('data/peers', 'w')
    print >> f, '127.0.0.1', '1234'
    f.close()

    if not os.path.isdir('data/data'):
        os.mkdir('data/data')
    f = open('data/data/peer.conf', 'w')
    print >> f, '1', '127.0.0.1', '1234', 'xyz'
    f.close()


    kargs = {}
    kargs['type'] = 'oneswarm'

    script = SearchScript(**kargs)
    script.next_testcase()

    os.chdir('data')

if __name__ == "__main__":
    from Tribler.dispersy.callback import Callback
    from Tribler.dispersy.dispersy import Dispersy

    callback = Callback()
    dispersy = Dispersy.get_instance(callback, u".", u":memory:")
    dispersy.statistics.enable_debug_statistics(True)

    callback.register(start_script)
    callback.loop()
