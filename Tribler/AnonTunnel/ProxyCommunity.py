from collections import defaultdict
from datetime import datetime, timedelta
import logging
from traceback import print_exc
from Tribler.AnonTunnel.ProxyConversion import BreakPayload, PingPayload
import sys

logger = logging.getLogger(__name__)

from Tribler.dispersy.candidate import BootstrapCandidate, Candidate

from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution

from ProxyConversion import CreatePayload, ProxyConversion, ExtendedPayload, DataPayload, ExtendPayload
from Observable import Observable
import functools


class ProxyCommunity(Community, Observable):
    def __init__(self, dispersy, master_member):
        Observable.__init__(self)

        # original walker callbacks (will be set during super(...).__init__)
        self._original_on_introduction_request = None
        self._original_on_introduction_response = None

        Community.__init__(self, dispersy, master_member)

        # Heartbeat hashmap Candidate -> last heart beat timestamp, assume we never heard any
        self.member_heartbeat = defaultdict(lambda: datetime.min)
        self.member_ping = defaultdict(lambda: datetime.min)

        self.subscribe("on_ping", lambda (event): logger.info("Got ping from %s:%d" % (event.message.candidate.sock_addr[0], event.message.candidate.sock_addr[1])))

        def ping_and_purge():
            try:
                while True:
                    timeout = 2.0

                    # Candidates we have sent a ping in the last timout seconds and havent returned a heat beat in another timeout seconds shall be purged
                    candidates_to_be_purged = \
                        {
                            candidate
                            for candidate in self.member_ping.keys()
                            if self.member_ping[candidate] < datetime.now() - timedelta(seconds=timeout)
                            and self.member_heartbeat[candidate] < self.member_ping[candidate] - timedelta(seconds=timeout)
                        }

                    for candidate in candidates_to_be_purged:
                        self.on_candidate_exit(candidate)
                        logger.error("CANDIDATE exit %s:%d" % (candidate.sock_addr[0], candidate.sock_addr[1]))

                    candidates_to_be_pinged = {candidate for candidate in self.member_heartbeat.keys() if self.member_heartbeat[candidate] < datetime.now() - timedelta(seconds=timeout)}.difference(candidates_to_be_purged)

                    for candidate in candidates_to_be_pinged:
                        self.send_ping(candidate.sock_addr)
                        logger.info("PING sent to %s:%d" % (candidate.sock_addr[0], candidate.sock_addr[1]))

                    # rerun over 10 second
                    yield 5.0
            except Exception, e:
                print_exc()
                logger.error(e)
                
        self.dispersy.callback.register(ping_and_purge, priority=-10)



    def initiate_conversions(self):
        return [DefaultConversion(self), ProxyConversion(self)]

    def initiate_meta_messages(self):
        def yield_all(messages):
            for msg in messages:
                yield msg

        def trigger_event(messages,event_name):
            for msg in messages:
                if msg.candidate in self.member_ping:
                    del self.member_ping[msg.candidate]

                self.member_heartbeat[msg.candidate] = datetime.now()
                self.fire(event_name, message=msg)

        return [
                Message(self,
                        u"ping",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        PingPayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_ping")),

                Message(self,
                        u"create",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        CreatePayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_create")),

                Message(self,
                        u"created",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        CreatePayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_created")),

                Message(self,
                        u"extend",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        ExtendPayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_extend")),

                Message(self,
                        u"extended",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        ExtendedPayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_extended")),

                Message(self,
                        u"data",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        DataPayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_data")),

                Message(self,
                        u"break",
                        NoAuthentication(),
                        PublicResolution(),
                        DirectDistribution(),
                        CandidateDestination(),
                        BreakPayload(),
                        yield_all,
                        functools.partial(trigger_event, event_name="on_break")),
                ]

    def _initialize_meta_messages(self):
        super(ProxyCommunity, self)._initialize_meta_messages()

        # replace the callbacks for the dispersy-introduction-request and
        # dispersy-introduction-response messages
        meta = self._meta_messages[u"dispersy-introduction-request"]
        self._original_on_introduction_request = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_request, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_request

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution, meta.distribution, meta.destination, meta.payload, meta.check_callback, self.on_introduction_response, meta.undo_callback, meta.batch)
        assert self._original_on_introduction_response

    def send_break(self, destination, circuit_id):
        """
        Send a BREAK message over a circuit

        :param destination: Destination address (the first hop) tuple (host, port), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :return: None
        """

        candidate = self.dispersy.get_candidate(destination)

        meta = self.get_meta_message(u"break")
        message = meta.impl(
                              distribution=(self.global_time,),
                              payload=(circuit_id,))

        self.dispersy.endpoint.send([candidate], [message.packet])

    def send_ping(self, destination):
        """
        Send a BREAK message over a circuit

        :param destination: Destination address (the first hop) tuple (host, port), must be a Dispersy Candidate!
        :return: None
        """

        candidate = self.dispersy.get_candidate(destination)
        self.member_ping[candidate] = datetime.now()

        meta = self.get_meta_message(u"ping")
        message = meta.impl(distribution=(self.global_time,))

        self.dispersy.endpoint.send([candidate], [message.packet])


    def send_create(self, destination, circuit_id):
        """
        Send a CREATE message over a circuit

        :param destination: Destination address (the first hop) tuple (host, port), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :return: None
        """
        candidate = self.dispersy.get_candidate(destination)

        meta = self.get_meta_message(u"create")
        message = meta.impl(  distribution=(self.global_time,),
                              payload=(circuit_id,))
        self.dispersy.endpoint.send([candidate], [message.packet])

    def send_created(self, destination, circuit_id):
        """
        Send a CREATED message over a circuit

        :param destination: Destination address (the first hop) tuple (host, port), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :return:
        """
        candidate = self.dispersy.get_candidate(destination)

        meta = self.get_meta_message(u"created")
        message = meta.impl(
                              distribution=(self.global_time,),
                              payload=(circuit_id,))
        self.dispersy.endpoint.send([candidate], [message.packet])

    def send_data(self, destination, circuit_id, ultimate_destination, data = None, origin = None):
        """
        Send a DATA message over a circuit

        :param destination: Destination address (the first hop) tuple (host, ip), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :param ultimate_destination: The ultimate destination of the message. Ordinarily a (host, port) outside the Dispersy
        community
        :param data: The data payload
        :param origin: The origin of the message, set only if from an external source.
        :return: None
        """
        candidate = self.dispersy.get_candidate(destination)

        meta = self.get_meta_message(u"data")
        message = meta.impl(
                              distribution=(self.global_time,),
                              payload=(circuit_id, ultimate_destination, data,origin))

        self.dispersy.endpoint.send([candidate], [message.packet])

    def send_extend(self, destination, circuit_id, extend_with):
        """
        Send an EXTEND message over a circuit

        :param destination: Destination address (the first hop) tuple (host, ip), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :param extend_with: The (host, port) to extend the circuit with
        :return: None
        """

        candidate = self.dispersy.get_candidate(destination)

        if not isinstance(candidate, Candidate):
            return

        meta = self.get_meta_message(u"extend")
        message = meta.impl(
                              distribution=(self.global_time,),
                              payload=(circuit_id, extend_with,))

        self.dispersy.endpoint.send([candidate], [message.packet])

    def send_extended(self, destination, circuit_id, extended_with):
        """
        Send an EXTENDED message over a circuit

        :param destination: Destination address (the first hop) tuple (host, ip), must be a Dispersy Candidate!
        :param circuit_id: The Circuit Id to use in communication
        :param extended_with: The new hop (host, port) that just joined the circuit
        :return: None
        """

        candidate = self.dispersy.get_candidate(destination)

        meta = self.get_meta_message(u"extended")
        message = meta.impl(
                              distribution=(self.global_time,),
                              payload=(circuit_id, extended_with,))

        self.dispersy.endpoint.send([candidate], [message.packet])

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    self.fire("on_member_heartbeat", candidate = message.candidate)

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            for message in messages:
                if not isinstance(message.candidate, BootstrapCandidate):
                    self.fire("on_member_heartbeat", candidate = message.candidate)

    def on_candidate_exit(self, candidate):
        if candidate in self.member_ping:
            del self.member_ping[candidate]

        if candidate in self.member_heartbeat:
            del self.member_heartbeat[candidate]

        self.fire("on_member_exit", member=candidate)