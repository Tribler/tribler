import sys
from hashlib import md5
from time import time
from random import getrandbits
from collections import defaultdict

DEBUG = True

# OneSwarm defaults
mForwardSearchProbability = 0.5
MAX_OUTGOING_SEARCH_RATE = 300
MAX_INCOMING_SEARCH_RATE = 1000 * 1.5

class OverlayManager:
    def __init__(self, community):
        self.community = community
        self.randomnessManager = RandomnessManager()

        self.receivedSearches = {}

        self.incomingSearchRate = defaultdict(lambda: Average(1000, 10))
        self.outgoingSearchRate = defaultdict(lambda: Average(1000, 10))

    def sendSearchOrCancel(self, search, skipQueue, forceSend):
        connections = self.community.get_wrapped_connections(10)
        if DEBUG:
            print >> sys.stderr, long(time()), "OverlayManager sending search/cancel to", len(connections), "connections"

        numSent = 0;
        for conn in connections:
            shouldSend = True
            if not forceSend:
                # Niels: not sure if this should be getSearchID() or using the keywords
                shouldSend = self.shouldForwardSearch(search.getSearchID(), conn)

            if shouldSend:
                if DEBUG:
                    print >> sys.stderr, "OverlayManager about to send a search to", conn
                self.sendSearch(conn, search, skipQueue)
                numSent += 1

                if DEBUG:
                    print >> sys.stderr, "OverlayManager sent a search to", conn

        # for searches sent by us, if we didn't send it to anyone try again but
        # without the randomness linitng who we are sending to
        if numSent == 0 and not forceSend:
            return self.sendSearchOrCancel(search, skipQueue, True)
        return connections

    def forwardSearchOrCancel(self, ignoreConn, msg):
        for connection in self.community.get_wrapped_connections(10, ignoreConn.dispersy_source):
            if DEBUG:
                print >> sys.stderr, long(time()), "OverlayManager forwarding search/cancel to:", connection

            if self.shouldForwardSearch(msg.getSearchID(), ignoreConn):
                self.sendSearch(connection, msg, False)

    def shouldForwardSearch(self, id, conn):
        if conn.getRemoteFriend().isCanSeeFileList():
            return True

        all = str(id) + conn.getRemotePublicKeyHash()
        randomVal = self.randomnessManager.getDeterministicRandomInt(all)
        if randomVal < 0:
            randomVal = -randomVal

        if randomVal < sys.maxint * mForwardSearchProbability:
            return True
        else:
            return False

    def sendSearch(self, connection, search, skipQueue):
        if (search.getSearchID(), connection.getRemotePublicKeyHash()) in self.receivedSearches:
            if DEBUG:
                print >> sys.stderr, long(time()), "OverlayManager not sending search, this search id is already received from this friend"
            return

        average = self.outgoingSearchRate[connection.getRemotePublicKeyHash()].getAverage()
        if average > MAX_OUTGOING_SEARCH_RATE:
            if DEBUG:
                print >> sys.stderr, long(time()), "OverlayManager dropping search, sending too fast"
            return

        self.outgoingSearchRate[connection.getRemotePublicKeyHash()].addValue(1);

        if DEBUG:
            print >> sys.stderr, long(time()), "OverlayManager forwarding text search:", search.getDescription()

        self.sendMessage(connection, search, skipQueue);

    def sendMessage(self, connection, message, skipQueue):
        self.community.send_wrapped(connection, message)

    def handleSearch(self, message, connection, callback):
        # possibleprune is always false for all incoming search messages
        # hence logic is removed

        self.incomingSearchRate[connection.getRemotePublicKeyHash()].addValue(1);
        average = self.incomingSearchRate[connection.getRemotePublicKeyHash()].getAverage()

        if average > MAX_INCOMING_SEARCH_RATE:
            if DEBUG:
                print >> sys.stderr, long(time()), "OverlayManager search spam detected, closing connection, friend banned for 10 min"
            return

        if DEBUG:
            print >> sys.stderr, long(time()), "OverlayManager incoming search. desc: ", connection.getNick(), ", rate=", average

        self.receivedSearches[(message.getSearchID(), connection.getRemotePublicKeyHash())] = time()
        return callback(connection, message)

class RandomnessManager:
    def __init__(self, secretBytes=None):
        if not secretBytes:
            self.secretBytes = getrandbits(20 * 8)
        else:
            self.secretBytes = secretBytes

    # returns a random int between 0 (inclusive) and n (exclusive) seeded by seedBytes
    def getDeterministicNextInt(self, seedlong, minValue, maxValue):
        randomInt = self.getDeterministicRandomInt(seedlong)
        if randomInt < 0:
            randomInt = -randomInt;

        return minValue + (randomInt % (maxValue - minValue))

    def getDeterministicRandomInt(self, seed):
        if self.secretBytes:
            # the implementation is slightly different to oneswarm, but basically does the same thing
            # first hash, then return the first 32 bits
            bitmask = (2 ** 32) - 1
            return long(md5(str(seed) + str(self.secretBytes)).hexdigest(), 16) & bitmask

    def getSecretBytes(self):
        return self.secretBytes

class Average:
    # refreshrate in ms, period in seconds
    def __init__(self, refreshRate, period):
        self.refreshRate = refreshRate / 1000
        self.period = period

        self.nbElements = self.period / self.refreshRate + 2
        self.lastUpdate = int(time() / self.refreshRate)
        self.values = [0] * self.nbElements

    def addValue(self, value):
        # we get the current time factor
        timeFactor = int(time() / self.refreshRate)

        # we first update the buffer
        self.update(timeFactor)

        # and then we add our value to the current element
        self.values[(timeFactor % self.nbElements)] += value

    def update(self, timeFactor):
        # If we have a really OLD lastUpdate, we could erase the buffer a
        # huge number of time, so if it's really old, we change it so we'll only
        # erase the buffer once.

        if self.lastUpdate < timeFactor - self.nbElements:
            self.lastUpdate = timeFactor - self.nbElements - 1;

        # For all values between lastUpdate + 1 (next value than last updated)
        # and timeFactor (which is the new value insertion position)
        for i in range(self.lastUpdate + 1, timeFactor):
            self.values[i % self.nbElements] = 0

        # We also clear the next value to be inserted (so on next time change...)
        self.values[(timeFactor + 1) % self.nbElements] = 0

        # And we update lastUpdate.
        self.lastUpdate = timeFactor

    def getAverage(self):
        return self.getSum() / float(self.period)

    def getSum(self):
        # We get the current timeFactor
        timeFactor = int(time() / self.refreshRate)

        # We first update the buffer
        self.update(timeFactor)

        # The sum of all elements used for the average.
        sum = 0

        # Starting on oldest one (the one after the next one)
        # Ending on last one fully updated (the one previous current one)
        for i in range(timeFactor + 2, timeFactor + self.nbElements + 1):
            # Simple addition
            sum += self.values[i % self.nbElements]

        return sum
