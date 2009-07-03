# Written by Jelle Roozenburg 
# see LICENSE.txt for license information
""" Controls the authorization of messages received via the Tribler Overlay """

from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.BitTornado.BT1.MessageID import *

DEBUG = False

MAX_QUERIES_FROM_RANDOM_PEER = 1000


class AbstractRequestPolicy:
    """ Superclass for all Tribler RequestPolicies. A RequestPolicy controls
    the authorization of messages received via the Tribler Overlay, such
    as distributed recommendations, remote queries, etc.
    """
    def __init__(self):
        """ Constructor """

    def allowed(self, permid, messageID):
        """ Returns whether or not the peer identified by permid is allowed to 
        send us a message of type messageID.
        @param permid The permid of the sending peer.
        @param messageID A integer messageID, see Tribler.Core.BitTornado.BT1.MessageID  
        @returns A boolean indicating whether the message is authorized.
        """
        raise NotYetImplementedException()


class AllowAllRequestPolicy(AbstractRequestPolicy):
    """ A RequestPolicy that allows all messages to be sent by all peers. """

    def allowed(self, permid, messageID):
        return self.allowAllRequestsAllPeers(permid, messageID)

    def allowAllRequestsAllPeers(self, permid, messageID):
        return True


class CommonRequestPolicy(AbstractRequestPolicy):    
    """ A base class implementing some methods that can be used as building 
    blocks for RequestPolicies. 
    """ 
    def __init__(self,session):
        """ Constructor """
        self.session = session
        self.friendsdb = session.open_dbhandler(NTFY_FRIENDS)
        self.peerdb = session.open_dbhandler(NTFY_PEERS)
        AbstractRequestPolicy.__init__(self)
    
    def isFriend(self, permid):
        """
        @param permid The permid of the sending peer. 
        @return Whether or not the specified permid is a friend.
        """
        fs = self.friendsdb.getFriendState(permid)
        return (fs == FS_MUTUAL or fs == FS_I_INVITED)

    def isSuperPeer(self, permid):        
        """
        @param permid The permid of the sending peer.
        @return Whether of not the specified permid is a superpeer.
        """
        return permid in self.session.lm.superpeer_db.getSuperPeers()

    def isCrawler(self, permid):
        """
        @param permid The permid of the sending peer.
        @return Whether of not the specified permid is a superpeer.
        """
        return permid in self.session.lm.crawler_db.getCrawlers()

    def benign_random_peer(self,permid):
        """
        @param permid The permid of the sending peer. 
        @return Whether or not the specified permid has exceeded his
        quota of remote query messages.
        """
        if MAX_QUERIES_FROM_RANDOM_PEER > 0:
            nqueries = self.get_peer_nqueries(permid)
            return nqueries < MAX_QUERIES_FROM_RANDOM_PEER
        else: 
            return True
    
    def get_peer_nqueries(self, permid):
        """
        @param permid The permid of the sending peer. 
        @return The number of remote query messages already received from
        this peer.
        """
        peer = self.peerdb.getPeer(permid)
        #print >>sys.stderr,"CommonRequestPolicy: get_peer_nqueries: getPeer",`permid`,peer
        #print >>sys.stderr,"CommonRequestPolicy: get_peer_nqueries: called by",currentThread().getName()
        if peer is None:
            return 0
        else:
            return peer['num_queries']

class AllowFriendsRequestPolicy(CommonRequestPolicy):
    """
    A RequestPolicy that allows all non-crawler messages to be sent by
    friends only. Crawler messages are allowed from Crawlers only.
    """

    def allowed(self, permid, messageID):
        if messageID in (CRAWLER_REQUEST, CRAWLER_REPLY):
            return self.isCrawler(permid)
        else:
            return self.allowAllRequestsFromFriends(permid, messageID)

    def allowAllRequestsFromFriends(self, permid, messageID):
        # Access control
        return self.isFriend(permid)


class FriendsCoopDLOtherRQueryQuotumCrawlerAllowAllRequestPolicy(CommonRequestPolicy):
    """
    Allows friends to send all messages related to cooperative
    downloads, subjects all other peers to a remote query quotum of
    100, and allows all peers to send all other non-crawler
    messages. Crawler messages are allowed from Crawlers only.
    """

    def allowed(self, permid, messageID):
        """ Returns whether or not the peer identified by permid is allowed to  
        send us a message of type messageID.
        @return Boolean. """
        if messageID == CRAWLER_REQUEST:
            return self.isCrawler(permid)
        elif (messageID in HelpCoordinatorMessages or messageID in HelpHelperMessages) and not self.isFriend(permid):
            return False
        elif messageID == QUERY and not (self.isFriend(permid) or self.benign_random_peer(permid)):
            return False
        else:
            return True

