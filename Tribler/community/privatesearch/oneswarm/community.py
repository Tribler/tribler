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

ENCRYPTION = True

class OneSwarmCommunity(TTLSearchCommunity):

    def __init__(self, master, integrate_with_tribler=True):
        TTLSearchCommunity.__init__(self, master, integrate_with_tribler)
        self.overlay_manager = OverlayManager(self)
        self.search_manager = SearchManager(self, self.overlay_manager)

    def initiate_meta_messages(self):
        messages = TTLSearchCommunity.initiate_meta_messages(self)
        messages.append(Message(self, u"search-cancel", MemberAuthentication(encoding="sha1"), PublicResolution(), DirectDistribution(), CandidateDestination(), SearchCancelPayload(), self._dispersy._generic_timeline_check, self.on_search_cancel))
        return messages

    def initiate_conversions(self):
        return [OneSwarmConversion(self)]

    def create_search(self, keywords, callback):
        identifier = self._dispersy.request_cache.generate_identifier()
        if self.log_searches:
            log("dispersy.log", "search-statistics", identifier=identifier, keywords=keywords, created_by_me=True)

        # create request message
        meta = self.get_meta_message(u"search-request")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier, 0, keywords, None))

        return self.search_manager.sendTextSearch(identifier, message, callback)

    def on_search(self, messages):
        for message in messages:
            # making datastructures compatible
            message = MessageWrapper(message)
            connection = SourceWrapper(self.community, message.candidate)

            self.overlay_manager.handleSearch(message, connection, self.search_manager.handleIncomingSearch)

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
            message = MessageWrapper(message)
            connection = SourceWrapper(self.community, message.candidate)

            self.search_manager.handleIncomingSearchResponse(connection, message)

    def _create_cancel(self, identifier):
        meta = self.get_meta_message(u"search-cancel")
        message = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(identifier))

        return message

    def on_search_cancel(self, messages):
        for message in messages:
            # making datastructures compatible
            message = MessageWrapper(message)
            connection = SourceWrapper(self.community, message.candidate)

            self.search_manager.handleIncomingSearchCancel(connection, message)

class MessageWrapper:
    def __init__(self, dispersy_msg):
        self.dispersy_msg = dispersy_msg

    def getDescription(self):
        return self.dispersy_msg.payload.keywords
    def getSearchString(self):
        return self.dispersy_msg.payload.keywords

    def getSearchID(self):
        return self.dispersy_msg.payload.identifier
    def getValueID(self):
        return self.__java_hashcode(self.getSearchString())

    def __java_hashcode(self, s):
        h = 0
        for c in s:
            h = (31 * h + ord(c)) & 0xFFFFFFFF
            return ((h + 0x80000000) & 0xFFFFFFFF) - 0x80000000

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
        return self.dispersy_source.get_members(self.community)[0].mid

class PoliOneSwarmCommunity(PoliForwardCommunity, OneSwarmCommunity):

    @classmethod
    def load_community(cls, master, my_member, integrate_with_tribler=True, encryption=ENCRYPTION, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        dispersy_database = DispersyDatabase.get_instance()
        try:
            dispersy_database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(master, my_member, my_member, integrate_with_tribler=integrate_with_tribler, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)
        else:
            return super(PoliOneSwarmCommunity, cls).load_community(master, integrate_with_tribler=integrate_with_tribler, encryption=encryption, log_searches=log_searches, use_megacache=use_megacache, max_prefs=max_prefs, max_fprefs=max_fprefs)

    def __init__(self, master, integrate_with_tribler=True, encryption=ENCRYPTION, log_searches=False, use_megacache=True, max_prefs=None, max_fprefs=None):
        OneSwarmCommunity.__init__(self, master, integrate_with_tribler)
        PoliForwardCommunity.__init__(self, master, integrate_with_tribler, encryption, 10, max_prefs, max_fprefs)

    def initiate_conversions(self):
        return PoliForwardCommunity.initiate_conversions(self) + OneSwarmCommunity.initiate_conversions(self)

    def initiate_meta_messages(self):
        return PoliForwardCommunity.initiate_meta_messages(self) + OneSwarmCommunity.initiate_meta_messages(self)
