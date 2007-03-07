# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

"""
Formulas: 
 P(I|U) = sum{U'<-I} P(U'|U)    # U' has I in his profile
   P(U'|U) = Sum{I}Pbs(U'|I)Pml(I|U)  # P2PSim
   Pbs(U|I) = (c(U,I) + mu*Pml(U))/(Sum{U}c(U,I) + mu)   # mu=1 by tuning on tribler dataset
   Pml(I|U) = c(U,I)/Sum{I}c(U,I)         
   Pml(U) = Sum{I}c(U,I) / Sum{U,I}c(U,I) 
   
Data Structur:
    preferences - U:{I|c(U,I)>0}, # c(U,I)    # Sum{I}c(U,I) = len(preferences[U])
    owners - I:{U|c(U,I)>0}    # I:I:Sum{U}c(U,I) = len(owners[I])
    userSim - U':P(U'|U)
    itemSim - I:P(I|U)
    total - Sum{U,I}c(U,I)     # Pml(U) = len(preferences[U])/total
    
Test:
    Using hash(permid) as user id, hash(infohash) as torrent id
    Incremental change == overall change
"""

from sets import Set

def P2PSim(pref1, pref2):
    """ Calculate similarity between peers """
    
    cooccurrence = len(Set(pref1) & Set(pref2))
    if cooccurrence == 0:
        return 0
    normValue = (len(pref1)*len(pref2))**0.5
    _sim = cooccurrence/normValue
    sim = int(_sim*1000)    # use integer for bencode
    return sim


class Recommender:
    def __init__(self, preferences, mypreflist):
        self.preferences = preferences  # {user: Set(prefs)}
        self.mypreflist = mypreflist    # [prefs]
        self.new_added_items = 0
        self.owners = {}                # {item_id: Set(users_id)}
        self.items = {}    # {hash(item): item}
        self.users = {}    # {hash(user): user}
        # after added some many (user, item) pairs, update sim of item to item
        self.update_threshold = 50  
        
#        # hash(torrent_id)<I'>: {hash(torrent_id)<I>: P(I'|I)} 
#        # P(I'|I)=sum_u{n(u,i,i')}/sum_u{n(u,i)} 
#        # where n(u,i) means u has item i, n(u,i,i') means user has both item i and i'.
#        # Sim(I',I) = (P(I'|I)*P(I|I'))**0.5
#        self.PII = {}

    def addUser(self, user_id, user):
        self.users[user_id] = user
    
    def addItem(self, item_id, item):
        self.items[item_id] = item
        
    def addOwner(self, item_id, user_id):
        if not self.owners.has_key(item_id):
            self.owners[item_id] = Set()
        if peer_id not in self.owners[item_id]:
            self.owners[item_id].add(peer_id)
            self.new_added_items += 1

    def checkUpdate(self):
        if self.new_added_items > self.update_threshold:
            self.update()
            self.new_added_items = 0
            
    def update(self):
        #TODO
        pass
    