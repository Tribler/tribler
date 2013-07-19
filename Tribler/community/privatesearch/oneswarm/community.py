from lencoder import log

from Tribler.community.privatesearch.community import TTLSearchCommunity
from Tribler.community.privatesemantic.community import PoliForwardCommunity
from Tribler.community.privatesearch.oneswarm.SearchManager import SearchManager
from Tribler.community.privatesearch.oneswarm.OverlayManager import OverlayManager

from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.dispersydatabase import DispersyDatabase
from Tribler.community.privatesearch.oneswarm.payload import SearchCancelPayload
from Tribler.community.privatesearch.oneswarm.conversion import OneSwarmConversion
from Tribler.dispersy.conversion import DefaultConversion

ENCRYPTION = True

class OneSwarmCommunity(TTLSearchCommunity):

    def __init__(self, master, integrate_with_tribler=True, log_searches=False, cancel_after=None):
        TTLSearchCommunity.__init__(self, master, integrate_with_tribler, log_searches=log_searches)
        self.overlay_manager = OverlayManager(self)
        self.search_manager = SearchManager(self, self.overlay_manager, cancel_after)

    def initiate_meta_messages(self):
        messages = TTLSearchCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"search-cancel", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchCancelPayload(), self._dispersy._generic_timeline_check, self.on_search_cancel))
        return messages

    def initiate_conversions(self):
        return [DefaultConversion(self), OneSwarmConversion(self)]

    def create_search(self, keywords, callback):
        identifier = self._dispersy.request_cache.generate_identifier()
        if self.log_searches:
            log("dispersy.log", "search-statistics", identifier=identifier, keywords=keywords, created_by_me=True)

        # create request message
        meta = self.get_meta_message(u"search-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier, 0, keywords, None))

        # create a callback converter
        def callback_converter(wrapped_msg):
            msg = wrapped_msg.dispersy_msg

            callback(keywords, msg.payload.results, msg.candidate)

        wrapped_candidates = self.search_manager.sendTextSearch(identifier, MessageWrapper(message, mine=True), callback_converter)
        return [wrapped_candidate.dispersy_source for wrapped_candidate in wrapped_candidates], [], identifier

    def on_search(self, messages):
        for message in messages:
            # making datastructures compatible
            connection = SourceWrapper(self, message.candidate)
            message = MessageWrapper(message)

            cycle = self.overlay_manager.handleSearch(message, connection, self.search_manager.handleIncomingSearch)
            if self.log_searches:
                log("dispersy.log", "search-statistics", identifier=message.dispersy_msg.payload.identifier, cycle=cycle)

    def send_response(self, original_request, single_result):
        original_request = original_request.dispersy_msg
        self._create_search_response(original_request.payload.identifier, [single_result], original_request.candidate)

    def forward_response(self, response_msg, connection):
        self._dispersy._send([connection.dispersy_source], [response_msg.dispersy_msg])

    def check_search_response(self, messages):
        for message in messages:
            accepted, _ = self._timeline.check(message)
            if not accepted:
                yield DelayMessageByProof(message)
                continue

            yield message

    def on_search_response(self, messages):
        for message in messages:
            # making datastructures compatible
            connection = SourceWrapper(self, message.candidate)
            message = MessageWrapper(message)

            self.search_manager.handleIncomingSearchResponse(connection, message)

    def _create_cancel(self, identifier, mine=False):
        meta = self.get_meta_message(u"search-cancel")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier,))

        return MessageWrapper(message, mine=mine)

    def on_search_cancel(self, messages):
        for message in messages:
            # making datastructures compatible
            connection = SourceWrapper(self, message.candidate)
            message = MessageWrapper(message)

            self.search_manager.handleIncomingSearchCancel(connection, message)

    def get_wrapped_connections(self, nr=10, ignore_candidate=None):
        return [SourceWrapper(self, connection) for connection in self.get_connections(nr, ignore_candidate)]

    def send_wrapped(self, connection, message):
        if not message.mine:
            self.search_forward += 1

        self.dispersy._send([connection.dispersy_source], [message.dispersy_msg])

class MessageWrapper:
    def __init__(self, dispersy_msg, mine=False):
        self.dispersy_msg = dispersy_msg
        self.mine = mine

    def getDescription(self):
        return " ".join(self.dispersy_msg.payload.keywords).strip()
    def getSearchString(self):
        return self.dispersy_msg.payload.keywords

    def getSearchID(self):
        return self.dispersy_msg.payload.identifier
    def getValueID(self):
        return self.__java_hashcode(self.getDescription())

    def __java_hashcode(self, s):
        h = 0
        for c in s:
            h = (31 * h + ord(c)) & 0xFFFFFFFF
            return ((h + 0x80000000) & 0xFFFFFFFF) - 0x80000000

    def getSize(self):
        return len(self.dispersy_msg.packet)

    def __str__(self):
        return str(self.dispersy_msg)

class SourceWrapper:
    def __init__(self, community, dispersy_source):
        self.community = community
        self.dispersy_source = dispersy_source

    def getRemoteFriend(self):
        return self

    def getNick(self):
        return str(self.dispersy_source)

    def isCanSeeFileList(self):
        return self.community.is_taste_buddy(self.dispersy_source)

    def getRemotePublicKeyHash(self):
        members = list(self.dispersy_source.get_members(self.community))
        if members:
            return members[0].mid
        return str(self.dispersy_source.sock_addr[1])

    def __str__(self):
        return str(self.dispersy_source)

class PoliOneSwarmCommunity(PoliForwardCommunity, OneSwarmCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None, cancel_after=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs, cancel_after=cancel_after)
        else:
            return super(PoliOneSwarmCommunity, cls).load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs, cancel_after=cancel_after)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None, cancel_after=None):
        OneSwarmCommunity.__init__(self, master, integrate_with_tribler, log_searches, cancel_after=cancel_after)
        PoliForwardCommunity.__init__(self, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs)

    def initiate_conversions(self):
        return PoliForwardCommunity.initiate_conversions(self) + OneSwarmCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PoliForwardCommunity.initiate_meta_messages(self) + OneSwarmCommunity.initiate_meta_messages(self)
