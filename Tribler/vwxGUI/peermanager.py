from Tribler.CacheDB.SynDBHandler import SynPeerDBHandler
from Tribler.CacheDB import CacheDBHandler
from Tribler.utilities import show_permid_shorter,sort_dictlist,remove_data_from_list,find_content_in_dictlist
from Tribler.unicode import *
import time
from safeguiupdate import *
import threading
from traceback import print_exc

DEBUG = True
def debug(message):
    if DEBUG:
        print message

def getAgeingValue(old_time):
    try:    
        old_time = int(old_time)
        if old_time < 0 :
            return 0
        curr_time = time()
        diff = int(curr_time - old_time)
    except: 
        return 0
    if diff < 60:
        return 6048 - diff
    elif diff < 3600:
        return 6048 - 60 + 6 - int(diff/10)
    if diff < 604800:
        return 6048 - 360 + 36 - int(diff/100)
    else:   
        return 0
    
class PeerDataManager(DelayedEventHandler):
    """offers a sync view of the peer database, in an usable form for the
    persons view and not only.
    it adds, deletes and updates data as soon as it is changed in database
    using the notifications system, and then informs the GUI of the changes
    that only has to use the data given by the manager; no new interrogation is needed"""
    # Code to make this a singleton
    __single = None
   
    def __init__(self):
        if PeerDataManager.__single:
            raise RuntimeError, "PeerDataManager is singleton"
        PeerDataManager.__single = self
        self.done_init = False
        DelayedEventHandler.__init__(self)
        self.doneflag = threading.Event()
        # for that, create a separate ordered list with only the first 20 most similar peers
        self.top20similar = []
#        self.count_AddData = 0
        self.MAX_CALLS = 50 #max number of calls that are done during an treat callback event
        ## initialization
        self.MIN_CALLBACK_INT = 1 #min callback interval: minimum time in seconds between two invocations on the gui from the callback
        self.start_callback_int = -1 #init the time variable for the callback function
        self.callback_dict = {} #empty list for events
        self.dict_guiCallbackFuncList = {}#callback function list from the parent, the creator object
#        self.guiCallbackFunc = updateFunc 
        self.peersdb = SynPeerDBHandler(updateFun = self.callbackPeerChange)#CacheDBHandler.PeerDBHandler()
        self.prefdb = CacheDBHandler.PreferenceDBHandler()
#        self.mydb = CacheDBHandler.MyPreferenceDBHandler()
#        self.tordb = CacheDBHandler.TorrentDBHandler()
        self.frienddb = CacheDBHandler.FriendDBHandler()
        self.MAX_MIN_PEERS_NUMBER = 1900
        self.MAX_MAX_PEERS_NUMBER = 2100

        self.data = self.prepareData()
        print "<mluc> have data"
        self.done_init = True
        
    def getInstance(*args, **kw):
        if PeerDataManager.__single is None:
            PeerDataManager(*args, **kw)       
        return PeerDataManager.__single
    getInstance = staticmethod(getInstance)
    
    def getPeerData(self, permid):
        for i in xrange(len(self.data)):
            if self.data[i]['permid'] == permid:
                return self.data[i]
        return None
    
    def isFriend(self, permid):
        peer_data = self.getPeerData(permid)
        if peer_data!=None and peer_data['friend']:
            return True
        return False
#        return self.frienddb.isFriend(permid)
    
    def setOnline(self, permid, bOnline):
        """sets online status for a peer given its permid"""
        peer_data = self.getPeerData(permid) 
        if peer_data == None:
            print "tried to set online status for",show_permid_shorter(permid),"to online?",bOnline
            return
        peer_data['online']=bOnline
        debug("%s is online? %s" %(peer_data['content_name'],peer_data['online']))
        if bOnline:
            mode="online"
        else:
            mode="offline"
        self.notifyGui(peer_data, mode)
        
    def addFriendwData(self, peer_data):
        permid = peer_data['permid']
        peer_d = self.getPeerData(permid)
        if peer_d!=None:
            peer_d['friend']=True
            peer_data['friend']=True
            self.frienddb.addFriend(permid)
            return True
        else:
            "Could not add as friend because not in cache"
        return False
    
    def addFriend(self, permid):
        peer_data = self.getPeerData(permid)
        if peer_data!=None:
            peer_data['friend']=True
            self.frienddb.addFriend(permid)
        else:
            "Could not add as friend because not in cache"

    def deleteFriend(self, permid):
        peer_data = self.getPeerData(permid)
        if peer_data!=None:
            peer_data['friend']=False
            self.frienddb.deleteFriend(permid)
        else:
            "Could not delete friend because not in cache"
        
    def prepareData(self):
        """prepares the data first time this manager is initialized
        for a peer it does the same things as preparePeer by duplicating the code for the moment"""
        # first, obtain values
        ##update
        #myprefs = self.mydb.getPrefList()
        peer_list = self.peersdb.getPeerList()
        key = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times', 'tried_times', 'port']
        tempdata = self.peersdb.getPeers(peer_list, key)

        self.MaxSimilarityValue = -1
        localdata = []
        #select only tribler peers
        for i in xrange(len(tempdata)):
            if tempdata[i].get('permid') and (tempdata[i]['connected_times'] > 0 or \
                         tempdata[i]['buddycast_times'] > 0):
                peer_data = tempdata[i]
                if peer_data['name']!=None and len(peer_data['name'])>0:
                    peer_data['content_name']=dunno2unicode(peer_data['name'])
                else:
                    peer_data['content_name']= 'peer %s' % show_permid_shorter(peer_data['permid'])#'[%s:%s]' % (localdata[i]['ip'],str(localdata[i]['port']))
                peer_data['friend'] = self.frienddb.isFriend(peer_data['permid'])#permid in self.friend_list
                # compute the maximal value for similarity
                # in order to be able to compute top-n persons based on similarity
                if peer_data.get('similarity'):
                    if peer_data['similarity']>self.MaxSimilarityValue:
                        self.MaxSimilarityValue = peer_data['similarity']
                else:
                    peer_data['similarity']=0
                #add infohash to be used by standardGrid.updateSelection
                #peer_data['infohash']=peer_data['permid']
                localdata.append(peer_data)
        
        # compute similarity rank based on similarity with this peer relative to the greatest similarity value
        #compute the similarity rank
        for i in xrange(len(localdata)):
            #compute the similarity percent
            localdata[i]['similarity_percent'] = int(localdata[i]['similarity']*100.0/self.MaxSimilarityValue)
        #save the data information
        return localdata

    def callbackPeerChange(self, permid, mode):
        """callback function to be notified when changes are made in the peers database
            mode is add, update or delete
        """
        start_time = time.time()
        #get updated peer data from database
        # mode = {add, update, delete}
        #return
        # instead of treating each message when it arrives, just put them in a hash
        # that has the permid as key and mode as value and when some time passed
        # invoke an event
        if self.start_callback_int == -1:
            self.start_callback_int = start_time
        self.callback_dict[permid] = mode
        if start_time - self.start_callback_int > self.MIN_CALLBACK_INT:
            treat_dict = {}
            count = 0
            for k,v in self.callback_dict.iteritems():
                treat_dict[k]=v
                count = count + 1
                if count >= self.MAX_CALLS:
                    break
            for k,v in treat_dict.iteritems():
                del self.callback_dict[k]
            #send the callback event
            #self.treatCallback(treat_dict)
            self.invokeLater(self.treatCallback, [treat_dict])
            #reset the start time
            self.start_callback_int = start_time
            #self.callback_dict = {}
            debug( "callback for %d persons" % len(treat_dict))
        return

    def treatCallback(self, permid_dict):
#        debug("treat callback with %d peers" % (len(permid_dict)))
        for permid, mode in permid_dict.iteritems():
            peer_data = None
            if mode in ['update', 'add']:
                #first get the new data from database
                peer_data = self.peersdb.getPeer(permid)
                #check if is a valid peer
                if (peer_data['connected_times'] == 0 and peer_data['buddycast_times'] == 0):
                    continue #skip this peer as it is of no interrest
                #extra check, the permid should already be there
                if peer_data.get('permid')==None:
                    peer_data['permid'] = permid
                #arrange the data some more: add content_name, rank and so on
                self.preparePeer(peer_data)
            #update local snapshot
            if mode == 'delete':
                remove_data_from_list(self.grid.data, permid)
            elif mode in ['update', 'add']:
                i = find_content_in_dictlist(self.data, peer_data, 'permid')
                if i != -1:
                    #update the data in local snapshot
                    self.data[i] = peer_data
                    #should reorder the data?
                else:
                    # shouldn't I insert the data at their place based on rank value... ?
                    self.data.append(peer_data)
                
            #inform the GuiUtility of operation
            try:
                self.notifyGui(peer_data, mode)
#                if self.guiCallbackFunc!=None:
#                    self.guiCallbackFunc(peer_data, mode)
            except:
                print "error calling GUI callback function for data change"
#            debug( "new operation to be done for %s in GuiUtility!" % peer_data['content_name'])
#===============================================================================
#            if mode in ['update', 'delete']:
#                 if self.detailPanel.showsPeer(permid):
#                     self.detailPanel.setData(peer_data)
#             
#            if mode in ['update', 'add']:
#                 self.addData(peer_data)
#            else:
#                 self.deleteData(permid)
#===============================================================================
    def notifyGui(self, peer_data, mode):
        """notifies all registered gui objects of the callback after the data is updated in database"""
        key = 'all' #the only type of key acceptable
        for func in self.dict_guiCallbackFuncList[key]:
            func(peer_data, mode)

    def preparePeer(self, peer_data):
        """when a peer is updated, prepare it for use inside the view
        creates content_name, similarity_percent, rank_value
        updates the global maximal similarity value and the list of top 20 most similar peers"""
        if peer_data['name']!=None and len(peer_data['name'])>0:
            peer_data['content_name']=dunno2unicode(peer_data['name'])
        else:
            peer_data['content_name']= 'peer %s' % show_permid_shorter(peer_data['permid'])#'[%s:%s]' % (localdata[i]['ip'],str(localdata[i]['port']))
        peer_data['friend'] = self.frienddb.isFriend(peer_data['permid'])#permid in self.friend_list
        # compute the maximal value for similarity
        # in order to be able to compute top-n persons based on similarity
        if peer_data.get('similarity'):
            if peer_data['similarity']>self.MaxSimilarityValue:
                self.MaxSimilarityValue = peer_data['similarity'] #should recompute percents
        else:
            peer_data['similarity']=0
        peer_data['similarity_percent'] = int(peer_data['similarity']*100.0/self.MaxSimilarityValue)
        #recompute rank
        peer_data['rank_value'] = self.compute_rankval(peer_data)
        #add infohash to be used by standardGrid.updateSelection
        #peer_data['infohash']=peer_data['permid']
        #check to see if top20 needs to be updated
        j = 0
        while j<len(self.top20similar):
            if self.top20similar[j]['similarity'] < peer_data['similarity']:
                break
            j = j+1
        self.top20similar.insert(j,peer_data)
        # check if too many
        if len(self.top20similar)>20:
            self.top20similar = self.top20similar[:20]

    def compute_rankval(self, peer_data):
        """computes a rank value for a peer used for ordering the peers based on
        friendship, similarity, name and last seen status 
        it codifies all these parameters on bits, in the order of significance:
        1bit + 7bits + 1bit + 13bits
        returns the number obtained, the bigger the number, higher the rank
        """
        rank_value = 0
        if peer_data.get('friend')!=None and peer_data['friend']==True:
            rank_value = rank_value + 1
        # add similarity
        rank_value = (rank_value << 7)
        if peer_data.get('similarity_percent')!= None:
            rank_value = rank_value + int(peer_data['similarity_percent'])
        # add name ordering
        rank_value = (rank_value << 1)
        if peer_data.get('content_name')!=None and not peer_data['content_name'].startswith('peer'):
            rank_value = rank_value + 1
        # add last seen
        rank_value = (rank_value << 13)
        if peer_data.get('last_seen')!= None:
            rank_value = rank_value + getAgeingValue(peer_data['last_seen'])
#        if DEBUG:
#            print "peer",peer_data['content_name'],(peer_data.get('friend') and "is" or "is not"),\
#            "friend, with a similarity of",peer_data['similarity_percent'],"%, and last seen",\
#            friendly_time(peer_data['last_seen']),"resulting rank value:",rank_value
        return rank_value

    def sortData(self, type=None):
        """ 
            gets the data, it orders it and if there is no data shows the 'searching_content' stub
            the ordering method is not based on only one criterion, but several
            based on the compute_rankval function
            it also limits the number of peers to 2000
            and after sorting it creates the top of 20st most similar peers
        """
        filtered = self.data
        for peer in filtered:
            peer['rank_value'] = self.compute_rankval(peer)
            
        filtered = sort_dictlist(filtered, 'rank_value', 'decrease')
        
        #if type is not none, use it
        if type == "friends":
            filtered = [item for item in filtered if item['friend']]
        
        self.top20similar = []
        for i in xrange(len(filtered)):
            j = 0
            while j<len(self.top20similar):
                if self.top20similar[j]['similarity'] < filtered[i]['similarity']:
                    break
                j = j+1
            self.top20similar.insert(j,filtered[i])
            # check if too many
            if len(self.top20similar)>20:
                self.top20similar = self.top20similar[:20]
        #limit the number of peers so that it wouldn't occupy alot of memory
        max_number = int((self.MAX_MAX_PEERS_NUMBER+self.MAX_MIN_PEERS_NUMBER)/2)
        if len(filtered)>max_number:
            filtered = filtered[:max_number]
#        if filtered:
#            self.neverAnyContent = False
#        elif self.neverAnyContent:
#            searchingContentStub = {'content_name':self.utility.lang.get('searching_content')}
#            filtered.append(searchingContentStub)
        self.data = filtered
        return filtered

    def getRank(self, permid):
        """looks for the current data in the top 20 list and returns the index starting from 1"""
        try:
            for i in range(len(self.top20similar)):
                if self.top20similar[i]['permid'] == permid:
                    return (i+1)
        except:
            pass
#            print "error on getting rank"
        return -1
    
    # register update function
    def register(self, func, key):
        try:
            key = key.lower()
            self.dict_guiCallbackFuncList[key].index(func)
            # if no exception, fun already exist!
            print "DBObserver register error. " + str(func.__name__) + " already exist!"
            return
        except KeyError:
            self.dict_guiCallbackFuncList[key] = []
            self.dict_guiCallbackFuncList[key].append(func)
        except ValueError:
            self.dict_guiCallbackFuncList[key].append(func)
        except Exception, msg:
            print "PeerDataManager unregister error.", Exception, msg
            print_exc()
        
    def unregister(self, func, key):
        try:
            key = key.lower()
            self.dict_guiCallbackFuncList[key].remove(func)
        except Exception, msg:
            print "PeerDataManager unregister error.", Exception, msg
            print_exc()
            
    def getPeerHistFiles(self, permid):
        """returns a list of hashes for the files this peer has in it's download history"""
        return self.prefdb.getPrefList(permid)