# Written by Niels Zeilemaker
# conversion of SearchManager.java from OneSwarm
import sys

from math import floor
from random import random, randint
from time import time, sleep
from threading import Thread
from traceback import print_exc
from collections import namedtuple
from Queue import Queue

DEBUG = False

# OneSwarm defaults
f2f_search_forward_delay = 150
NO_FORWARD_FRAC_OF_MAX_UPLOAD = 0.9
NO_RESPONSE_TOTAL_FRAC_OF_MAX_UPLOAD = 0.9
NO_RESPONSE_TRANSPORT_FRAC_OF_MAX_UPLOAD = 0.75
NO_RESPONSE_TORRENT_AVERAGE_RATE = 10000

MAX_SEARCH_QUEUE_LENGTH = 100
MAX_OUTGOING_SEARCH_RATE = 300
MAX_SEARCH_AGE = 60

mMIN_RESPONSE_DELAY = 1
mMAX_RESPONSE_DELAY = 2

mMIN_DELAY_LINK_LATENCY = 1
mMAX_DELAY_LINK_LATENCY = 2

class SearchManager:

    def __init__(self, community, overlayManager, cancel_after=None):
        self.community = community
        self.overlayManager = overlayManager

        self.sentSearches = {}
        self.forwardedSearches = {}
        self.canceledSearches = {}
        self.recentSearches = set()
        self.delayedSearchQueue = DelayedSearchQueue(self, f2f_search_forward_delay)

        self.bloomSearchesBlockedCurr = 0
        self.bloomSearchesSentCurr = 0
        self.forwardedSearchNum = 0
        self.lastSearchAccountingFlush = time()

        if cancel_after:
            self.mMaxSearchResponsesBeforeCancel = cancel_after
        else:
            self.mMaxSearchResponsesBeforeCancel = 40

    def sendTextSearch(self, newSearchId, msg, callback):
        return self.sendSearch(newSearchId, msg, callback, True, False)

    def sendSearch(self, newSearchId, search, callback, skipQueue, forceSend):
        self.sentSearches[newSearchId] = SentSearch(search, callback)
        return self.overlayManager.sendSearchOrCancel(search, skipQueue, forceSend);

    def handleIncomingSearch(self, source, msg):
        if DEBUG:
            print >> sys.stderr, long(time()), "SearchManager got search:", msg.getDescription()

        if msg.getSearchID() in self.forwardedSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager message already forwarded"
            return True
        if msg.getSearchID() in self.sentSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager message is mine"
            return True
        if self.delayedSearchQueue.isQueued(msg):
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager message is scheduled to be forwarded"
            return True

        # only implementing textsearch
        shouldForward = self.handleTextSearch(source, msg)

        # check if we are at full capacity
        if not self.canForwardSearch():
            shouldForward = False

        if shouldForward:
            # ok, seems like we should attempt to forward this, put it in
            # the queue
            self.delayedSearchQueue.add(source, msg)

        return False

    def handleTextSearch(self, source, msg):
        shouldForward = True
        if DEBUG:
            print >> sys.stderr, long(time()), "SearchManager handleTextSearch:", msg.getDescription(), "from", source.getRemoteFriend().getNick()

        searchString = msg.getSearchString()

        # removed filtering, modified call to get results
        results = self.community._get_results(searchString, None, False)
        if DEBUG:
            print >> sys.stderr, long(time()), "SearchManager found matches", len(results)

        if len(results) > 0:
            if self.canRespondToSearch():
                for result in results:
                    task = DelayedSearchResponse(msg, result, self, self.community)
                    delay = self.getSearchDelayForInfohash(source.getRemoteFriend())

                    self.community.dispersy.callback.register(task.run, delay=(delay / 1000.0))
            else:
                shouldForward = False
        return shouldForward


    """
     There are 2 possible explanations for getting a search response, either
     we got a response for a search we sent ourselves, or we got a response
     for a search we forwarded
    """
    def handleIncomingSearchResponse(self, source, msg):
        sentSearch = self.sentSearches.get(msg.getSearchID(), None)

        # first, if might be a search we sent
        if sentSearch:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager got response to search:", sentSearch.getSearch().getDescription()

            # update response stats
            sentSearch.gotResponse()

            # check if we got enough search responses to cancel this search
            # we will still use the data, even if the search is canceled. I
            # mean, since it already made it here why not use it...

            if sentSearch.getResponseNum() > mMaxSearchResponsesBeforeCancel:
                # only send a cancel message once
                sendCancel = False
                if msg.getSearchID() not in self.canceledSearches:
                    self.canceledSearches[msg.getSearchID()] = time()

                    if DEBUG:
                        print >> sys.stderr, long(time()), "SearchManager canceling search", msg
                    sendCancel = True;

                if sendCancel:
                    self.overlayManager.sendSearchOrCancel(self.community._create_cancel(msg.getSearchID(), mine=True), True, False)

            sentSearch.callback(msg)

        # sentsearch == null
        else:
            # ok, this is for a search we forwarded
            search = self.forwardedSearches.get(msg.getSearchID(), None)
            if search == None:
                # Search responses after 60 seconds are dropped (not that unusual)
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchManager got response for slow/unknown search:", source, ":", msg.getDescription()
                return

            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager got response to forwarded search:", search.getSearch().getDescription()

            if msg.getSearchID() in self.canceledSearches:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchManager not forwarding search, it is already canceled,", msg.getSearchID()
                return

            searcher = search.getSource()
            responder = source
            if search.getResponseNum() > mMaxSearchResponsesBeforeCancel:
                # we really shouldn't cancel other peoples searches, but if
                # they don't do it we have to
                self.canceledSearches[msg.getSearchID()] = time()

                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchManager sending cancel for someone elses search!, searcher=", searcher.getRemoteFriend(), " responder=", responder.getRemoteFriend(), ":\t", search

                self.overlayManager.forwardSearchOrCancel(source, self.community._create_cancel(msg.getSearchID()))

            else:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchManager forwarding response to", searcher.getRemoteFriend(), " responder=", responder.getRemoteFriend()

                # assuming honest connections during this experiment, not implementing overlay registering
                search.gotResponse()

                # send out the search
                self.community.forward_response(msg, searcher)

    def handleIncomingSearchCancel(self, source, msg):
        forward = False

        # if this is the first time we see the cancel, check if we
        # forwarded this search, if we did, send a cancel

        if msg.getSearchID() not in self.canceledSearches:
            self.canceledSearches[msg.getSearchID()] = time()

            # we only forward the cancel if we already sent the search
            if msg.getSearchID() in self.forwardedSearches:
                forward = True;
            else:
                if DEBUG:
                    print >> sys.stderr, long(time()), "SearchManager got search cancel for unknown search id"

        if forward:
            self.overlayManager.forwardSearchOrCancel(source, msg)

    def forwardSearch(self, source, search):
        # check if search is canceled or forwarded first
        searchID = search.getSearchID();
        if searchID in self.forwardedSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager not forwarding search, already forwarded. id:", searchID
            return

        if searchID in self.canceledSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager not forwarding search, cancel received. id:", searchID
            return

        valueID = search.getValueID();
        if (searchID, valueID) in self.recentSearches:
            self.bloomSearchesBlockedCurr += 1
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager not forwarding search, in recent filter. id:", searchID
            return

        self.bloomSearchesSentCurr += 1
        self.forwardedSearchNum += 1
        if DEBUG:
            print >> sys.stderr, long(time()), "SearchManager forwarding search", search.getDescription(), "id:", searchID

        self.forwardedSearches[searchID] = ForwardedSearch(source, search)
        self.recentSearches.add((searchID, valueID))

        self.overlayManager.forwardSearchOrCancel(source, search)

    def canForwardSearch(self):
        util = self.fracUpload()
        if util == -1 or util < NO_FORWARD_FRAC_OF_MAX_UPLOAD:
            return True
        else:
            if DEBUG:
                print >> sys.stderr, long(time()), "SearchManager not forwarding search (overloaded, util=", util, ")"
            return False

    def canRespondToSearch(self):
        totalUtil = self.fracUpload()
        if totalUtil == -1:
            return True

        # ok, check if we are using more than 90% of total
        if totalUtil < NO_RESPONSE_TOTAL_FRAC_OF_MAX_UPLOAD:
            return True

        transUtil = self.fracTransportUpload()
        # check if we are using more than 75% for transports
        if transUtil < NO_RESPONSE_TRANSPORT_FRAC_OF_MAX_UPLOAD:
            return True

        torrentAvgSpeed = self.getAverageUploadPerRunningTorrent()
        if torrentAvgSpeed == -1:
            return True

        if torrentAvgSpeed > NO_RESPONSE_TORRENT_AVERAGE_RATE:
            return True

        if DEBUG:
            print >> sys.stderr, long(time()), "SearchManager not responding to search (overloaded, util=", transUtil, ")"
        return False

    def isSearchCanceled(self, searchID):
        return searchID in self.canceledSearches

    def fracUpload(self):
        # TODO: fill some sane numbers here
        return -1

    def fracTransportUpload(self):
        # TODO: fill some sane numbers here
        return -1

    def getAverageUploadPerRunningTorrent(self):
        # TODO: fill some sane numbers here
        return -1

    def getSearchDelayForInfohash(self, destination):
        if destination.isCanSeeFileList():
            return 0.0
        else:
            searchDelay = randint(mMIN_RESPONSE_DELAY, mMAX_RESPONSE_DELAY)
            latencyDelay = randint(mMIN_DELAY_LINK_LATENCY, mMAX_DELAY_LINK_LATENCY)
            return float(searchDelay + latencyDelay)

class DelayedSearchResponse:
    def __init__(self, msg, result, search_manager, community):
        self.msg = msg
        self.result = result
        self.search_manager = search_manager
        self.community = community

    def run(self):
        if DEBUG:
            print >> sys.stderr, "DelayedSearchResponse, attempting to send search response", self.msg.getSearchID(), self.result

        if not self.search_manager.isSearchCanceled(self.msg.getSearchID()):
            if DEBUG:
                print >> sys.stderr, "DelayedSearchResponse, sending search response", self.msg.getSearchID(), self.result
            self.community.send_response(self.msg, self.result)

class ForwardedSearch:
    def __init__(self, source, search):
        self.source = source
        self.search = search

        self.responsesForwarded = 0
        self.initialized = time()

    def getAge(self):
        return time() - self.initialized

    def getResponseNum(self):
        return self.responsesForwarded

    def getSearch(self):
        return self.search

    def getSearchId(self):
        return self.search.getSearchID()

    def getSource(self):
        return self.source

    def gotResponse(self):
        self.responsesForwarded += 1

    def isTimedOut(self):
        return self.getAge() > MAX_SEARCH_AGE;

class SentSearch:
    def __init__(self, search, callback):
        self.search = search
        self.callback = callback
        self.responses = 0
        self.initialized = time()

    def getSearch(self):
        return self.search

    def getAge(self):
        return time() - self.initialized

    def getResponseNum(self):
        return self.responses

    def gotResponse(self):
        self.responses += 1

    def isTimedOut(self):
        return self.getAge() > MAX_SEARCH_AGE

class DelayedSearchQueue:
    def __init__(self, searchManager, delay):
        self.searchManager = searchManager
        self.mDelay = delay

        self.lastSearchesPerSecondLogTime = 0
        self.searchCount = 0;
        self.lastBytesPerSecondCount = 0;

        self.queue = Queue()
        self.queuedSearches = {}
        self.searchesPerFriend = {}

        self.t = DelayedSearchQueueThread(searchManager, self.queue, self.queuedSearches, self.searchesPerFriend)
        self.t.start()

    def add(self, source, search):
        if self.lastSearchesPerSecondLogTime + 1 < time():
            if DEBUG:
                print >> sys.stderr, long(time()), "DelayedSearchQueue searches/sec:", self.searchCount, "bytes:", self.lastBytesPerSecondCount, "searchQueueSize:", len(self.queuedSearches)

            self.lastSearchesPerSecondLogTime = time()
            self.searchCount = 0
            self.lastBytesPerSecondCount = 0

        self.searchCount += 1
        self.lastBytesPerSecondCount += search.getSize()

        # Flush the accounting info every 60 seconds
        if self.searchManager.lastSearchAccountingFlush + 60 < time():
            self.searchManager.lastSearchAccountingFlush = time()
            self.searchesPerFriend.clear()

        # If the search queue is more than half full, start dropping searches
        # proportional to how much of the total queue each person is consuming
        if len(self.queuedSearches) > 0.25 * MAX_SEARCH_QUEUE_LENGTH:
            if source.getRemoteFriend() in self.searchesPerFriend:
                outstanding = self.searchesPerFriend[source.getRemoteFriend()].v

                # We add a hard limit on the number of searches from any one person.
                if outstanding > 0.15 * MAX_SEARCH_QUEUE_LENGTH:
                    if DEBUG:
                        print >> sys.stderr, long(time()), "DelayedSearchQueue dropping due to 25% of total queue consumption", source.getRemoteFriend().getNick(), outstanding, "/", MAX_SEARCH_QUEUE_LENGTH
                    return

                # In other cases, we drop proportional to the consumption of the overall queue.
                acceptProb = float(outstanding) / float(len(self.queuedSearches))
                if random() < acceptProb:
                    if DEBUG:
                        print >> sys.stderr, long(time()), "DelayedSearchQueue *** RED for search from", source, "outstanding:", outstanding, "total:", len(self.queuedSearches)
                    return


        if len(self.queuedSearches) > MAX_SEARCH_QUEUE_LENGTH:
            if DEBUG:
                print >> sys.stderr, long(time()), "DelayedSearchQueue not forwarding search, queue length too large. id:", search.getSearchID()
            return

        if search.getSearchID() not in self.queuedSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "DelayedSearchQueue adding search to forward queue, will forward in " , self.mDelay, "ms"

            entry = DelayedSearchQueueEntry(search, source, time() + (self.mDelay / 1000.0))

            if source.getRemoteFriend() not in self.searchesPerFriend:
                self.searchesPerFriend[source.getRemoteFriend()] = MutableInteger()
            self.searchesPerFriend[source.getRemoteFriend()].v += 1

            if DEBUG:
                print >> sys.stderr, long(time()), "DelayedSearchQueue search for friend:", source.getRemoteFriend().getNick(), self.searchesPerFriend[source.getRemoteFriend()].v

            self.queuedSearches[search.getSearchID()] = entry
            self.queue.put(entry);
        elif DEBUG:
            print >> sys.stderr, long(time()), "DelayedSearchQueue search already in queue, not adding"

    def isQueued(self, search):
        return search.getSearchID() in self.queuedSearches

class DelayedSearchQueueThread(Thread):
    def __init__(self, searchManager, queue, queuedSearches, searchesPerFriend):
        Thread.__init__(self)
        self.searchManager = searchManager
        self.queue = queue
        self.queuedSearches = queuedSearches
        self.searchesPerFriend = searchesPerFriend

    def run(self):
        while True:
            try:
                e = self.queue.get()
                timeUntilSend = e.dontSendBefore - time()
                timeUntilSend *= 1000  # convert back to ms
                if timeUntilSend > 0:
                    if DEBUG or True:
                        print >> sys.stderr, long(time()), "DelayedSearchQueueThread: got search (", e.search.getDescription(), ") to forward, waiting ", timeUntilSend, "ms until sending"
                    sleep(timeUntilSend / 1000.0)  # convert back to s

                self.searchManager.forwardSearch(e.source, e.search)

                # remove the search from the queuedSearchesMap
                del self.queuedSearches[e.search.getSearchID()]

                # searchesPerFriend could have been  flushed while this
                # search was in the queue
                if e.source.getRemoteFriend() in self.searchesPerFriend:
                    self.searchesPerFriend[e.source.getRemoteFriend()].v -= 1

                # if we didn't sleep at all, sleep the min time between searches
                if timeUntilSend < 1:
                    ms = 1000.0 / MAX_OUTGOING_SEARCH_RATE
                    msFloor = int(floor(ms))
                    nanosLeft = int(round((ms - msFloor) * 1000000.0))

                    # we need to convert to seconds, as python accepts floats in sleep
                    sleepSeconds = (msFloor / 1000.0) + (nanosLeft / 1000000000.0)

                    if DEBUG or True:
                        print >> sys.stderr, long(time()), "DelayedSearchQueueThread sleeping", msFloor, "ms", nanosLeft, "ns or", sleepSeconds, "seconds in python-speak"

                    sleep(sleepSeconds)

            except:
                print_exc()

class DelayedSearchQueueEntry:
    def __init__(self, search, source, dontSendBefore):
        self.insertionTime = time()
        self.search = search
        self.source = source
        self.dontSendBefore = dontSendBefore

class MutableInteger:
    def __init__(self):
        self.v = 0
