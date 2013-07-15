import sys

from community import SearchCommunity, PSearchCommunity, HSearchCommunity
from Tribler.dispersy.script import ScenarioScriptBase
from Tribler.dispersy.member import Member
from Tribler.dispersy.tool.lencoder import log
from Tribler.dispersy.dispersy import IntroductionRequestCache


class SearchScript(ScenarioScriptBase):

    def __init__(self, **kargs):
        ScenarioScriptBase.__init__(self, 'barter.log', **kargs)

        self.late_join = int(kargs.get('latejoin', 1000))
        self.community_type = kargs.get('type', 'search')
        self.community_kargs = {}
        if 'ttl' in kargs:
            self.community_kargs['ttl'] = kargs['ttl']
        if 'neighbors' in kargs:
            self.community_kargs['neighbors'] = int(kargs['neighbors'])
        if 'max_prefs' in kargs:
            self.community_kargs['max_prefs'] = int(kargs['max_prefs'])

        def str2bool(v):
            return v.lower() in ("yes", "true", "t", "1")

        self.manual_connect = str2bool(kargs.get('manual_only', 'false'))
        self.bootstrap_percentage = float(kargs.get('bootstrap_percentage', 1.0))
        self.search_limit = int(kargs.get('search_limit', sys.maxsize))
        self.community_kargs['encryption'] = str2bool(kargs.get('encryption', 'false'))

        self.taste_buddies = set()
        self.not_connected_taste_buddies = set()
        self.nr_search = 0

        self.did_reply = set()
        self.test_set = set()
        self.test_reply = set()

    def join_community(self, my_member):
        self.my_member = my_member

        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404f10c33b03d2a09943d6d6a4b2cf4fe3129e5dce1df446a27d0ce00d48c845a4eff8102ef3becd6bc07c65953c824d227ebc110016d5ba71163bf6fb83fde7cdccf164bb007e27d07da952c47d30cf9c843034dc7a4603af3a84f8997e5d046e6a5f1ad489add6878898079a4663ade502829577c7d1e27302a3d5ea0ae06e83641a093a87465fdd4a3b43e031a9555".decode("HEX")
        master = Member(master_key)

        log(self._logfile, "joining community with kargs", kargs=self.community_kargs)

        if self.community_type == 'search':
            community = SearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches= True, **self.community_kargs)
        elif self.community_type == 'hsearch':
            community = HSearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches= True, **self.community_kargs)
        else:
            community = PSearchCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler=False, log_searches= True, **self.community_kargs)

        self._add_taste_buddies = community.add_taste_buddies
        community.add_taste_buddies = self.log_taste_buddies

        self._manual_create_introduction_request = community.create_introduction_request
        if self.manual_connect:
            community.create_introduction_request = lambda destination, allow_sync: self._manual_create_introduction_request(destination, False)

        if int(self._my_name) <= self.late_join:
            self._create_introduction_request = community.create_introduction_request
            community.create_introduction_request = lambda *args: None

        self._dispersy.callback.register(self.monitor_taste_buddy, delay=1.0)

        return community

    def do_steps(self):
        self._dispersy.callback.register(self.log_statistics, delay=1.0)
        return ScenarioScriptBase.do_steps(self)

    def get_commands_from_fp(self, fp, step):
        if step == 100 and int(self._my_name) <= self.late_join:
            self._community.create_introduction_request = self._create_introduction_request

        if (self._community.ttl or self._community.forwarding_prob) and step > 0 and step % 100 == 0:
            nr_search = step / 100
            if nr_search <= self.search_limit:
                self.nr_search = nr_search
                self._dispersy.callback.persistent_register("do_search", self.perform_searches)

        return ScenarioScriptBase.get_commands_from_fp(self, fp, step)

    def execute_scenario_cmds(self, commands):
        for command in commands:
            cur_command = command.split()
            if cur_command[0] == 'download':
                infohash = cur_command[1]
                infohash = infohash + " " * (20 - len(infohash))

                log(self._logfile, "registering download %s" % infohash)
                self._community._mypref_db.addMyPreference(infohash, {})

            elif cur_command[0] == 'testset':
                infohash = cur_command[1]
                infohash = infohash + " " * (20 - len(infohash))

                self.test_set.add(infohash)
                self._community._mypref_db.addTestPreference(infohash)

            elif cur_command[0] == 'taste_buddy':
                peer_id = int(cur_command[1])
                ip, port = self.get_peer_ip_port(peer_id)

                self.taste_buddies.add((ip, port))
                self.not_connected_taste_buddies.add((ip, port))

                # connect to first 10
                if len(self.taste_buddies) <= (10 * self.bootstrap_percentage):
                    log(self._logfile, "new taste buddy %s:%d" % (ip, port))

                    if int(self._my_name) > self.late_join:
                        self._dispersy.callback.register(self.connect_to_taste_buddy, args=((ip, port),), delay = 1.0)

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
            recall /= float(self._nr_peers)

            log("dispersy.log", "scenario-statistics", bootstrapped=taste_ratio, latejoin= latejoin, recall = recall, nr_search_ = self.nr_search)
            log("dispersy.log", "scenario-debug", not_connected=list(self.not_connected_taste_buddies), search_forward= self._community.search_forward, search_forward_success = self._community.search_forward_success, search_forward_timeout = self._community.search_forward_timeout, search_endpoint = self._community.search_endpoint, search_cycle_detected = self._community.search_cycle_detected, search_megacachesize = self._community.search_megacachesize, create_time_encryption = self._community.create_time_encryption, create_time_decryption = self._community.create_time_decryption, receive_time_encryption = self._community.receive_time_encryption)
            yield 5.0

    def log_taste_buddies(self, new_taste_buddies):
        self._add_taste_buddies(new_taste_buddies)

        for taste_buddy in new_taste_buddies:
            log(self._logfile, "new taste buddy", sim=taste_buddy[0], sock=str(taste_buddy[-1]), is_tb=self._community.is_taste_buddy(taste_buddy[-1]))

            if taste_buddy[-1].sock_addr in self.not_connected_taste_buddies and not self._community.is_taste_buddy(taste_buddy[-1]):
                log(self._logfile, "currentlist", list=[map(str, tup) for tup in self._community.taste_buddies])

            self.did_reply.add(taste_buddy[-1].sock_addr)

    def log_search_response(self, keywords, results, candidate):
        for result in results:
            if result[0] in self.test_set:
                self.test_reply.add(result[0])

        recall = len(self.test_reply) / float(len(self.test_set))
        if results:
            log(self._logfile, "results", recall=recall, keywords= keywords, candidate = str(candidate), results = results)
        else:
            log(self._logfile, "no results", recall=recall, keywords= keywords, candidate = str(candidate))

    def monitor_taste_buddy(self):
        while True:
            for sock_addr in self.taste_buddies:
                if self._community.is_taste_buddy_sock(sock_addr):
                    if sock_addr in self.not_connected_taste_buddies:
                        self.not_connected_taste_buddies.remove(sock_addr)
                else:
                    self.not_connected_taste_buddies.add(sock_addr)
            yield 5.0

    def connect_to_taste_buddy(self, sock_addr):
        candidate = self._community.get_candidate(sock_addr, replace=False)
        if not candidate:
            candidate = self._community.create_candidate(sock_addr, False, sock_addr, sock_addr, u"unknown")

        while not self._community.is_taste_buddy(candidate):
            log(self._logfile, "sending introduction request to %s" % str(candidate))
            self._manual_create_introduction_request(candidate, True)

            yield IntroductionRequestCache.timeout_delay + IntroductionRequestCache.cleanup_delay

    def perform_searches(self):
        for infohash in (self.test_set - self.test_reply):
            candidates, local_results = self._community.create_search([unicode(infohash)], self.log_search_response)
            candidates = map(str, candidates)
            log(self._logfile, "send search query for '%s' to %d candidates" % (infohash, len(candidates)), candidates= candidates)

            if local_results:
                self.log_search_response([unicode(infohash)], local_results, None)

            yield 5.0
