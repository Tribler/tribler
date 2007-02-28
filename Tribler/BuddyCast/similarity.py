# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

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