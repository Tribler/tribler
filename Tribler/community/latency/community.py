from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.candidate import Candidate
from payload import PingPayload, PongPayload, RequestLatenciesPayload, ResponseLatenciesPayload
from conversion import LatencyConversion
import time
import logging
from collections import OrderedDict
import pickle

logger = logging.getLogger(__name__)

class LatencyCommunity(Community):
    @classmethod
    def get_master_members(cls, dispersy):
        """
        KEP
        generated: Wed May 17 14:42:28 2017
        curve: None
        len: 571 bits ~ 144 bytes signature
        pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000403e9bf5b066aa0b488864ee6959abb6e74946ac21eff057af9f420b1fe423f5cd30456edfc217663d288b976a83c7eeb38c250ccd47d1535de4afd5e34d3de3946a731b09dd187660397a02a8c10eea7ee993e4dba780e76bdd22f3fa569640197b6115d10b0e65a5be39b623d131bede7a357d4140919518b9c9a9bac6f2ae8bffad3e09d40849ae262244408fa4137
        prv: 241 3081ee020101044803709b9530aa1ce6c24213735e42a0edb65289f8f050d65a8a90895be6eb199393e627588dd50577629f9ef32454e05f15898ec7e7685e07e233ee902c84b7b6f2cf458b3518e163a00706052b81040027a18195038192000403e9bf5b066aa0b488864ee6959abb6e74946ac21eff057af9f420b1fe423f5cd30456edfc217663d288b976a83c7eeb38c250ccd47d1535de4afd5e34d3de3946a731b09dd187660397a02a8c10eea7ee993e4dba780e76bdd22f3fa569640197b6115d10b0e65a5be39b623d131bede7a357d4140919518b9c9a9bac6f2ae8bffad3e09d40849ae262244408fa4137
        pub-sha1 16d7134d47dba19cc161cf230add499ad25288f7
        prv-sha1 1ca7cdd48c352d6c54c6d0c11f113b3da4795900
        -----BEGIN PUBLIC KEY-----
        MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQD6b9bBmqgtIiGTuaVmrtudJRqwh7/
        BXr59CCx/kI/XNMEVu38IXZj0oi5dqg8fus4wlDM1H0VNd5K/V400945RqcxsJ3R
        h2YDl6AqjBDup+6ZPk26eA52vdIvP6VpZAGXthFdELDmWlvjm2I9Exvt56NX1BQJ
        GVGLnJqbrG8q6L/60+CdQISa4mIkRAj6QTc=
        -----END PUBLIC KEY-----
        -----BEGIN EC PRIVATE KEY-----
        MIHuAgEBBEgDcJuVMKoc5sJCE3NeQqDttlKJ+PBQ1lqKkIlb5usZk5PmJ1iN1QV3
        Yp+e8yRU4F8ViY7H52heB+Iz7pAshLe28s9FizUY4WOgBwYFK4EEACehgZUDgZIA
        BAPpv1sGaqC0iIZO5pWau250lGrCHv8Fevn0ILH+Qj9c0wRW7fwhdmPSiLl2qDx+
        6zjCUMzUfRU13kr9XjTT3jlGpzGwndGHZgOXoCqMEO6n7pk+Tbp4Dna90i8/pWlk
        AZe2EV0QsOZaW+ObYj0TG+3no1fUFAkZUYucmpusbyrov/rT4J1AhJriYiRECPpB
        Nw==
        -----END EC PRIVATE KEY-----
        :param dispersy: 
        :return: 
        """
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403e9bf5b066aa0b488864ee6959abb6e74946ac21eff057af9f420b1fe423f5cd30456edfc217663d288b976a83c7eeb38c250ccd47d1535de4afd5e34d3de3946a731b09dd187660397a02a8c10eea7ee993e4dba780e76bdd22f3fa569640197b6115d10b0e65a5be39b623d131bede7a357d4140919518b9c9a9bac6f2ae8bffad3e09d40849ae262244408fa4137".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initialize(self, tribler_session = None):
        super(LatencyCommunity, self).initialize()
        self.latencies = OrderedDict()
        self.crawled_latencies = {}
        self.pingtimes = {}
        self.pings = []
        self.pongs = []
        self.relays = {}
        self.use_local_address = True

        logger.info("Latency community initialized")

    def initiate_meta_messages(self):
        return super(LatencyCommunity, self).initiate_meta_messages() + [
            Message(self, u"ping",
                    MemberAuthentication(encoding="sha1"),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    #CommunityDestination(node_count=10)
                    PingPayload(),
                    self.check_message,
                    self.on_ping),
            Message(self, u"pong",
                    MemberAuthentication(encoding="sha1"),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    PongPayload(),
                    self.check_message,
                    self.on_pong),
            Message(self, u"request_latencies",
                    MemberAuthentication(encoding="sha1"),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    RequestLatenciesPayload(),
                    self.check_message,
                    self.on_request_latencies),
            Message(self, u"response_latencies",
                    MemberAuthentication(encoding="sha1"),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    ResponseLatenciesPayload(),
                    self.check_message,
                    self.on_response_latencies),
        ]

    def initiate_conversions(self):
        return [DefaultConversion(self), LatencyConversion(self)]

    def check_message(self, messages):
        for message in messages:
            yield message

    def get_dispersy_address(self):
        """
        Returns the address of the Dispersy instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.dispersy.lan_address if self.use_local_address else self.dispersy.wan_address

    def send_ping(self):
        """
        Send ping messages towards all known neighbors.
        """
        for address in self.candidates:
            candidate = self.candidates[address]
            to_ip = candidate.sock_addr[0]
            to_port = candidate.sock_addr[1]
            # Do not send a ping message to localhost.
            if to_ip == '127.0.0.1': continue

            # Save current time to do a latency measurement.
            self.pingtimes[(to_ip,to_port)] = time.time()
            payload = self.get_dispersy_address() + (str(self.pingtimes[(to_ip,to_port)]),)

            self._logger.debug("Send ping message towards ip %s and port %s from ip %s and port %s", to_ip, to_port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

            meta = self.get_meta_message(u"ping")
            message = meta.impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                payload=payload,
                destination=(candidate,),
            )
            self.dispersy._forward([message])

    def on_ping(self, messages):
        for message in messages:
            ip = message.payload.ip
            port = message.payload.port
            self._logger.debug("Ping received from ip %s and port %s on ip %s and port %s", ip, port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

            assert isinstance(ip, str)
            assert isinstance(port, int)
            assert isinstance(message.payload.time, str)

            # Check whether ping message is not send from self and was not already received.
            if not (message.payload.ip == self.get_dispersy_address()[0] and message.payload.port == self.get_dispersy_address()[1]) and (message.payload.ip, message.payload.port, message.payload.time) not in self.pings:
                self.pings.append((message.payload.ip,message.payload.port, message.payload.time))
                ip = message.payload.ip
                port = message.payload.port

                # Add sender to discovered candidates.
                candidate = Candidate((ip,port), False)
                self.add_discovered_candidate(candidate)

                # Send pong message.
                payload = self.get_dispersy_address() + (message.payload.time,)
                self._logger.debug("Pong send towards ip %s and port %s from ip %s and port %s", ip, port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])
                meta = self.get_meta_message(u"pong")
                message = meta.impl(
                    authentication=(self.my_member,),
                    distribution=(self.claim_global_time(),),
                    payload=payload,
                    destination=(candidate,),
                )
                self.dispersy._forward([message])

    def on_pong(self, messages):
        for message in messages:
            from_ip = message.payload.ip
            from_port = message.payload.port

            assert isinstance(from_ip, str)
            assert isinstance(from_port, int)
            assert isinstance(message.payload.time, str)

            self._logger.debug("Pong received from ip %s and port %s on ip %s and port %s", from_ip, from_port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

            # Check whether pong was not already received.
            if (from_ip, from_port, message.payload.time) not in self.pongs:
                self.pongs.append((from_ip, from_port, message.payload.time))
                # Calculate new latency.
                self.latencies[(from_ip,from_port)] = time.time() - self.pingtimes[(from_ip,from_port)]
                self._logger.debug("New latency calculated for ip %s and port %s on ip %s and port %s", from_ip, from_port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

    def get_recent_seen_latencies(self):
        """
        :return: The latest latencies calculated of (ip, port) combinations.
        :rtype: OrderedDict()
        """
        return self.latencies

    def get_new_relay_id(self):
        """
        :return: Global time variable
        :rtype: int
        """
        return self._global_time

    def crawl_latencies(self):
        """
        Send a request to crawl latencies to neighbouring peers.
        """
        self.crawled_latencies = {}
        payload = self.get_dispersy_address() + (0, [self.get_new_relay_id()])

        self._logger.debug("Send latency request message from ip %s and port %s",
                           self.get_dispersy_address()[0], self.get_dispersy_address()[1])

        meta = self.get_meta_message(u"request_latencies")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload,
        )
        self.dispersy._forward([message])

    def on_request_latencies(self, messages):
        for message in messages:
            ip = message.payload.ip
            port = message.payload.port
            relay_list = message.payload.relay_list
            hops = message.payload.hops

            assert isinstance(ip, str)
            assert isinstance(port, int)
            assert isinstance(relay_list, list)
            assert isinstance(hops, int)

            # Save ip port combination of sender for a later relay lookup when responding with latencies.
            self.relays[relay_list[hops]] = (ip,port)

            self._logger.debug("Latency crawl request received from ip %s and port %s on ip %s and port %s", ip, port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

            # Add sender to discovered candidates.
            candidate = Candidate((ip, port), False)
            self.add_discovered_candidate(candidate)

            # Send latencies back towards sender.
            payload = self.get_dispersy_address() + (pickle.dumps(self.latencies), relay_list[:-1])
            self._logger.debug("Response with latencies for crawl request send from ip %s and port %s on ip %s and port %s", ip, port, self.get_dispersy_address()[0], self.get_dispersy_address()[1])

            meta = self.get_meta_message(u"response_latencies")
            message = meta.impl(
                authentication=(self.my_member,),
                distribution=(self.claim_global_time(),),
                payload=payload,
                destination=(candidate,),
            )
            self.dispersy._forward([message])

            # Forward latency request if the number of hops is less than 2. Hops represents how many times the latency request has been forwarded.
            if hops < 2:
                relay_list.append(self.get_new_relay_id())
                payload = self.get_dispersy_address() + (hops + 1, relay_list)

                self._logger.debug("Latency crawl request forwarded from ip %s and port %s",
                                   self.get_dispersy_address()[0], self.get_dispersy_address()[1])

                meta = self.get_meta_message(u"request_latencies")
                message = meta.impl(
                    authentication=(self.my_member,),
                    distribution=(self.claim_global_time(),),
                    payload=payload,
                )
                self.dispersy._forward([message])

    def on_response_latencies(self, messages):
        for message in messages:
            relay_list = message.payload.relay_list
            # If the relay list is empty, the latency response message is received at the peer who send the crawl request. Else the latency response has to be forwarded.
            if len(relay_list) == 0:
                latencies = pickle.loads(message.payload.latencies)
                # Update the crawled latencies dictionary.
                self.crawled_latencies.update(latencies)
                self._logger.debug("New latencies of crawl request received on ip %s and port %s",
                                   self.get_dispersy_address()[0], self.get_dispersy_address()[1])
            else:
                # Lookup the next peer to where the latency response is forwared.
                candidate = Candidate(self.relays[relay_list.pop()], False)
                self.add_discovered_candidate(candidate)

                self._logger.debug("Latencies of crawl request forwarded toward ip %s and port %s on ip %s and port %s", candidate.sock_addr[0], candidate.sock_addr[1],
                                   self.get_dispersy_address()[0], self.get_dispersy_address()[1])

                payload = (message.payload.ip, message.payload.port, message.payload.latencies, relay_list)
                meta = self.get_meta_message(u"response_latencies")
                message = meta.impl(
                    authentication=(self.my_member,),
                    distribution=(self.claim_global_time(),),
                    payload=payload,
                    destination=(candidate,),
                )
                self.dispersy._forward([message])