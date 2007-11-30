# Written by Jelle Roozenburg 
# see LICENSE.txt for license information
""" Controls the authorization of messages received via the Tribler Overlay """

import sys
from Tribler.Core.exceptions import *
from Tribler.Core.BitTornado.BT1.MessageID import *

DEBUG = True

MAX_QUERIES_FROM_RANDOM_PEER = 1000


class AbstractRequestPolicy:
	""" Superclass for all Tribler RequestPolicies. A RequestPolicy controls
	the authorization of messages received via the Tribler Overlay, such
	as distributed recommendations, remote queries, etc.
	"""
	def __init__(self, launchmany):
		""" Constructor """
		self.launchmany = launchmany
	
	def allowed(self, permid, messageID):
		""" Returns whether or not the peer identified by permid is allowed to 
		send us a message of type messageID.
		@param permid The permid of the sending peer.
		@param messageID A integer messageID, see Tribler.Core.BitTornado.BT1.MessageID  
		@returns A boolean indicating whether the message is authorized.
		"""
		raise NotYetImplementedException()
	

class CommonRequestPolicy(AbstractRequestPolicy):	
	""" A base class implementing some methods that can be used as building 
	blocks for RequestPolicies. 
	""" 
	def __init__(self, launchmany):
		""" Constructor """
		AbstractRequestPolicy.__init__(self,launchmany)
	
	def isFriend(self, permid):
		"""
		@param permid The permid of the sending peer. 
		@return Whether or not the specified permid is a friend.
		"""
		friends = self.launchmany.friend_db.getFriends()
		friend_permids = [peer['permid'] for peer in friends]
		return permid in fried_permids

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
		peer = self.launchmany.peer_db.getPeer(permid)
		return peer['nqueries']
    

class AllowAllRequestPolicy(CommonRequestPolicy):
	""" A RequestPolicy that allows all messages to be sent by all peers. """

	def allowed(self, permid, messageID):
		return self.allowAllRequestsAllPeers(permid, messageID)
	
	def allowAllRequestsAllPeers(self, permid, messageID):
		return True
	
	
class AllowFriendsRequestPolicy(CommonRequestPolicy):
	""" A RequestPolicy that allows all messages to be sent by friends only. """

	def allowed(self, permid, messageID):
		return self.allowAllRequestsFromFriends(permid, messageID)
	
	def allowAllRequestsFromFriends(self, permid, messageID):
		# Access control
	    return self.isFriend(permid)


class FriendsCoopDLOtherRQueryQuotumAllowAllRequestPolicy(CommonRequestPolicy):
	""" Allows friends to send all messages related to cooperative downloads,
	subjects all other peers to a remote query quotum of 100, and allows
	all peers to send all other messages. 
	"""

	def allowed(self, permid, messageID):
		""" Returns whether or not the peer identified by permid is allowed to  
		send us a message of type messageID. """
		if (messageID in HelpCoordinatorMessages or messageID in HelpHelperMessages) and not isFriend(permid):
			return False
		elif messageID == QUERY and not (isFriend(permid) or benign_random_peer(permid)):
			return False
		else:
			return True
		
