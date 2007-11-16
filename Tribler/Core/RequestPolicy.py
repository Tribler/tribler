# Written by Jelle Roozenburg 
# see LICENSE.txt for license information

import sys
#import Tribler.Core.API
import triblerAPI

DEBUG = True

MAX_QUERIES_FROM_RANDOM_PEER = 1000




class AbstractRequestPolicy:
	def __init__(self, launchmany):
		self.launchmany = launchmany
	
	def allowed(self, permid, messageType):
		raise triblerAPI.NotYetImplementedException()
	
	
	#============ Help methods ====================
	
	def isFriend(self, permid):
		friends = self.launchmany.friend_db.getFriends()
		friend_permids = [peer['permid'] for peer in friends]
		return permid in fried_permids



	def benign_random_peer(self,permid):
		if MAX_QUERIES_FROM_RANDOM_PEER > 0:
			nqueries = self.get_peer_nqueries(permid)
			return nqueries < MAX_QUERIES_FROM_RANDOM_PEER
		else: 
			return True
	
	def get_peer_nqueries(self, permid):
		peer = self.launchmany.peer_db.getPeer(permid)
		return peer['nqueries']
    

class AllowAllRequestPolicy(AbstractRequestPolicy):
	def allowed(self, permid, messageType):
		return self.allowAllRequestsAllPeers(permid, messageType)
	
	def allowAllRequestsAllPeers(self, permid, messageType):
		return True
	
class AllowFriendsRequestPolicy(AbstractRequestPolicy):
	def allowed(self, permid, messageType):
		return self.allowAllRequestsFromFriends(permid, messageType)
	
	def allowAllRequestsFromFriends(self, permid, messageType):
		# Access control
	    return self.isFriend(permid)
