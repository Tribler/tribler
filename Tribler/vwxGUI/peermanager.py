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
    
#===============================================================================
# def swap(array, index1, index2):
#    aux = array[index1]
#    array[index1] = array[index2]
#    array[index2] = aux
#    
# def partition(array, left, right, pivotIndex, key, orderMode):
#    pivotValue = array[pivotIndex][key]
#    swap( array, pivotIndex, right) # Move pivot to end
#    storeIndex = left
#    for i in range(left,right):
#        if (orderMode=='descending' and array[i][key] >= pivotValue) or ( orderMode!='descending' and array[i][key] <= pivotValue):
#            swap( array, storeIndex, i)
#            storeIndex = storeIndex + 1
#    swap( array, right, storeIndex) # Move pivot to its final place
#    return storeIndex
# 
# def quicksort(array, left, right, key, orderMode):
#    if right > left:
#        #select a pivot index (e.g. pivotIndex = left)
#        pivotIndex = left
#        pivotNewIndex = partition(array, left, right, pivotIndex, key, orderMode)
#        quicksort(array, left, pivotNewIndex-1, key, orderMode)
#        quicksort(array, pivotNewIndex+1, right, key, orderMode)
# 
# def sortInPlace(list, key='permid', orderMode='descending'):
#    """apply a sorting algorithm without creating a new list"""
#    quicksort(list, 0, len(list)-1, key, orderMode)
#===============================================================================
    
class PeerDataManager(DelayedEventHandler):
    """offers a sync view of the peer database, in an usable form for the
    persons view and not only.
    it adds, deletes and updates data as soon as it is changed in database
    using the notifications system, and then informs the GUI of the changes
    that only has to use the data given by the manager; no new interrogation is needed"""
    # Code to make this a singleton
    __single = None
   
    def __init__(self, utility):
        if PeerDataManager.__single:
            raise RuntimeError, "PeerDataManager is singleton"
        PeerDataManager.__single = self
        self.done_init = False
        DelayedEventHandler.__init__(self)
        self.doneflag = threading.Event()
        self.isDataPrepared = False
        self.utility = utility
        # for that, create a separate ordered list with only the first 20 most similar peers
        self.top20similar = []
        self.MaxSimilarityValue = 0 #maximal value for similarity as maintained 
        #by the peer manager; it increases if a new or updated peer has a greater 
        #value, but it doesn't decreases if the peer is deleted... should it? then a recomputation is neccessary
        self.MAX_CALLS = 50 #max number of calls that are done during an treat callback event
        ## initialization
        self.MIN_CALLBACK_INT = 1 #min callback interval: minimum time in seconds between two invocations on the gui from the callback
        self.start_callback_int = -1 #init the time variable for the callback function
        self.callback_dict = {} #empty list for events
        self.dict_guiCallbackFuncList = {}#callback function list from the parent, the creator object
        self.peersdb = SynPeerDBHandler(updateFun = self.callbackPeerChange)#CacheDBHandler.PeerDBHandler()
        self.prefdb = CacheDBHandler.PreferenceDBHandler()
#        self.mydb = CacheDBHandler.MyPreferenceDBHandler()
#        self.tordb = CacheDBHandler.TorrentDBHandler()
        self.frienddb = CacheDBHandler.FriendDBHandler()
        self.MAX_MIN_PEERS_NUMBER = 1900
        self.MAX_MAX_PEERS_NUMBER = 2100

        #there should always be an all key that contains all data
        self.data = [] #this all data can also be stored in a separate variable for easier usage
        self.filtered_data = { 'all':self.data}
        #there should anways be no filtering function for this all data
        self.filtered_func = { 'all':(None,None) } #a sorting function can be added later
        noDataStub = {'content_name':self.utility.lang.get('persons_view_no_data'), 'permid':'000001'}#, 'similarity':0}
        self.data.append(noDataStub)

        #this initialization can be done in another place also
        data = self.prepareData()
        self.sortData(data)
        #self.filtered_data['all'] = data
        self.applyFilters(data)
#        self.data = self.filtered_data['all'] 
        self.isDataPrepared = True
        self.done_init = True
        
    def getInstance(*args, **kw):
        if PeerDataManager.__single is None:
            PeerDataManager(*args, **kw)       
        return PeerDataManager.__single
    getInstance = staticmethod(getInstance)
    
    def applyFilter(self, filter_name, source_data=None):
        """regenerates the data list of the filter based on the source data or all data if source is not provided"""
        data = self.filtered_data[filter_name]
        #first clear data in filters
        while len(data)>0:
            data.pop()
        func = self.filtered_func[filter_name][0]
        if source_data is None:
            source_data = self.filtered_data['all']
        for item in source_data:
            if func is None or func(item):
                data.append(item)
    
    def applyFilters(self, localdata):
        """should fill all data lists based on the filter functions defined [and then sort them...]"""
        for type in self.filtered_data.keys():
            #filter data
            self.applyFilter(type, localdata)
            if type == 'all':
                self.data = self.filtered_data['all']
            
    def insertInFilters(self, peer_data):
        """inserts in each filtered data the value at the right position based on the comparing function
        if compare function is None, append at the end"""
        for type,list in self.filtered_data.iteritems():
            filterFunc,cmpFunc = self.filtered_func[type]
            if filterFunc is None or filterFunc(peer_data):
                print "adding peer",peer_data['content_name'],"to filter",type
                self.insertInPlace(list, peer_data, cmpFunc)
            
    def removeFromFilters(self, permid):
        """inserts in each filtered data the value at the right position based on the comparing function
        if compare function is None, append at the end"""
        for type,list in self.filtered_data.iteritems():
            peer_index = self.getPeerDataIndex(permid, type)
            if peer_index != -1:
                #check if it stays in the list
                filterFunc = self.filtered_func[type][0]
                if filterFunc is not None and not filterFunc(list[peer_index]):
                    #remove it from this filtered list
                    list.pop(peer_index)
    
    def getPeerDataIndex(self, permid, filter_name='all'):
        if self.filtered_data.get(filter_name) is None:
            return -1
        data = self.filtered_data[filter_name] 
        for i in xrange(len(data)):
            if data[i]['permid'] == permid:
                return i
        return -1
    
    def getPeerData(self, permid, filter_name='all'):
        if self.filtered_data.get(filter_name) is None:
            return None
        data = self.filtered_data[filter_name] 
        for i in xrange(len(data)):
            if data[i].get('permid') is None:
                print "<mluc> ERROR: peer has no permid!!!!"
                print "<mluc> ERROR: peer name is",data[i]['content_name']
            if data[i]['permid'] == permid:
                return data[i]
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
        if peer_data is None:
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
            self.insertInFilters(peer_d)
            return True
        else:
            "Could not add as friend because not in cache"
        return False
    
    def addFriend(self, permid):
        peer_data = self.getPeerData(permid)
        if peer_data!=None:
            peer_data['friend']=True
            self.frienddb.addFriend(permid)
            self.insertInFilters(peer_data)
        else:
            "Could not add as friend because not in cache"

    def deleteFriend(self, permid):
        peer_data = self.getPeerData(permid)
        if peer_data!=None:
            peer_data['friend']=False
            self.frienddb.deleteFriend(permid)
            self.removeFromFilters(permid)
        else:
            "Could not delete friend because not in cache"

    def deleteFriendwData(self, peer_data):
        permid = peer_data['permid']
        peer_d = self.getPeerData(permid)
        if peer_d!=None:
            peer_d['friend']=False
            peer_data['friend']=False
            self.frienddb.deleteFriend(permid)
            self.removeFromFilters(permid)
            return True
        else:
            "Could not delete friend because not in cache"
        return False
        
        
    def prepareData(self, peer_list=None):
        """it receives an optional peer_list parameter with the list of permids that should be the peers
        prepares the data first time this manager is initialized
        for a peer it sets up some data by calling preparePeer"""        
        # first, obtain values
        ##update
        #myprefs = self.mydb.getPrefList()
        if peer_list is None:
            peer_list = self.peersdb.getPeerList()
        key = ['permid', 'name', 'ip', 'similarity', 'last_seen', 'connected_times', 'buddycast_times', 'port']
        tempdata = self.peersdb.getPeers(peer_list, key)

        localdata = []
        #select only tribler peers
        for i in xrange(len(tempdata)):
            if tempdata[i].get('permid') and tempdata[i]['connected_times'] > 0:
                peer_data = tempdata[i]
                self.preparePeer(peer_data)
                localdata.append(peer_data)
    
        #compute the top similarity list
        self.updateTopList(localdata, self.top20similar, 'similarity')
        # compute similarity rank based on similarity with this peer relative to the greatest similarity value
        #compute the similarity rank
#===============================================================================
#        for i in xrange(len(localdata)):
#            #compute the similarity percent
#            localdata[i]['similarity_percent'] = int(localdata[i]['similarity']*100.0/self.MaxSimilarityValue)
#===============================================================================
        #save the data information
        return localdata

    def computeSimilarityPercent(self, similarity_value):
        """used to get a live value for similarity percent as it shouldn't be stored in the peer data"""
        if self.MaxSimilarityValue > 0:
            return int(similarity_value*100.0/self.MaxSimilarityValue)
        return 0 #if no maximal value computed yet, there is no percentage available

    def callbackPeerChange(self, permid, mode):
        """callback function to be notified when changes are made in the peers database
            mode is add, update or delete
        """
        start_time = time.time()
        #get updated peer data from database
        # mode = {add, update, delete, hide}
        #return
        # instead of treating each message when it arrives, just put them in a hash
        # that has the permid as key and mode as value and when some time passed
        # invoke an event
        if self.start_callback_int == -1:
            self.start_callback_int = start_time
        self.callback_dict[permid] = mode
        if start_time - self.start_callback_int > self.MIN_CALLBACK_INT and self.isDataPrepared:
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
                if peer_data.get('permid') is None:
                    peer_data['permid'] = permid
                #arrange the data some more: add content_name, rank and so on
                self.preparePeer(peer_data)
            #update local snapshot
            if mode in ['delete', 'hide']:
                #remove from all lists
                for key, list in self.filtered_data.iteritems():
                    remove_data_from_list(list, permid)
            elif mode in ['update', 'add']:
                if peer_data is not None:
                    self.insertInFilters(peer_data)
#===============================================================================
#                i = find_content_in_dictlist(self.data, peer_data, 'permid')
#                if i != -1:
#                    #update the data in local snapshot
#                    self.data[i] = peer_data
#                    #should reorder the data?
#                else:
#                    # shouldn't I insert the data at their place based on rank value... ?
# #                    self.data.append(peer_data)
#                    #append data to all lists
#                    for key,list in self.filtered_data.iteritems():
#                        if not self.filtered_func[key] or self.filtered_func[key] and self.filtered_func[key](peer_data):
#                            list.append( peer_data)
#===============================================================================
                
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
        if self.dict_guiCallbackFuncList.has_key(key):
            for func in self.dict_guiCallbackFuncList[key]:
                func(peer_data, mode)
  
    def updateTopList(self, data_list, top_list, key, equal_key='permid', max_list_length=20):
        """for each element in data_list, add it to top_list ordered descending based on the key
        it returns true or false if changes have been made to top_list"""
        bChange = False
        for element in data_list:
            #check where to add the element, and also where is already inserted
            index = 0
            llen = len(top_list)
            indexInsertAt = llen
            indexIsAt = -1
            while index < llen:
                if top_list[index][equal_key] == element[equal_key]:
                    indexIsAt = index
                if top_list[index][key] < element[key]:
                    indexInsertAt = index
                if indexIsAt != -1 and indexInsertAt < llen:
                    break #both indexes are computed so no reason to continue
                index = index + 1
            if indexInsertAt != indexIsAt: #if on the same position, do nothing
                if indexIsAt != -1 and indexIsAt < llen-1 and element[key] == top_list[indexIsAt+1][key]:
                    continue #if is equal with the ones until insertion point, no need to do it
                if indexIsAt != -1:
                    #move from one position to another
                    top_list.pop(indexIsAt)
                    if indexIsAt < indexInsertAt:
                        indexInsertAt = indexInsertAt - 1
                    bChange = True #there is a change in the list
                if indexInsertAt < max_list_length: #don't insert an element that will be removed
                    top_list.insert(indexInsertAt, element)
                    bChange = True #there is a change in the list
            #reduce the size of the list
            while len(top_list)>max_list_length:
                top_list.pop()
        #print len(top_list), [ elem['content_name'] for elem in top_list]
        return bChange

    def updatePeer(self, old_value, new_value):
        """updates an existing peer data dictionary with values from a new one while keeping the old reference"""
        for key,value in new_value.iteritems():
            old_value[key] = value
            
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
#===============================================================================
#        if self.isDataPrepared:
#            if self.MaxSimilarityValue > 0:
#                peer_data['similarity_percent'] = int(peer_data['similarity']*100.0/self.MaxSimilarityValue)
#            else:
#                peer_data['similarity_percent'] = 0
#            #recompute rank
#            peer_data['rank_value'] = self.compute_rankval(peer_data)
#===============================================================================
        #check to see if top20 needs to be updated
        if self.updateTopList([peer_data], self.top20similar, 'similarity'):
            #refresh the grid
            pass

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

    def cmpFuncSimilarity( val1, val2):
        """compare function that sorts on similarity value"""
        if val1['similarity'] > val2['similarity']:
            return 1
        elif val1['similarity'] < val2['similarity']:
            return -1
        return 0
    
    def sortData(self, localdata=None, filter='all'):
        """ 
            it sorts data based on similarity
            data can be a list provided as a parameter or as a type from the self.filtered_data dictionary
            it also limits the number of peers to 2000
            it sorts the data in place, that means without creating another list, so no return value
            
            type can either be 'friends' or other. 
        """
        if localdata is not None:
            filtered = localdata
        else:
            filtered = self.filtered_data[filter]
#        for peer in filtered:
#            peer['rank_value'] = self.compute_rankval(peer)
        #get sort function
        cmpFunc = self.filtered_func[filter][1]
        if cmpFunc is not None:
            self.sortInPlace( filtered, cmpFunc)
        
        #limit the number of peers so that it wouldn't occupy alot of memory
        if len(filtered)>self.MAX_MAX_PEERS_NUMBER:
            while len(filtered)>self.MAX_MIN_PEERS_NUMBER:
                filtered.pop()
        
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
    
    def registerFilter(self, name, filterFunc=None, cmpFunc=None):
        """maintains an updated list of items that, when called with filterFunc return true
        it also retains the sorting function for this filter and sorts the data
        returns a reference to the list"""
        if name != 'all':
            self.filtered_data[name] = []
            self.filtered_func[name] = (filterFunc,cmpFunc)
            self.applyFilter(name)
            if cmpFunc!=None:
                self.sortData(name)
        return self.filtered_data[name]
        
    # register update function
    def register(self, func, key, filterFunc=None, cmpFunc=None):
        """when updates are made to data, inform the registered handlers"""
        self.registerFilter( key, filterFunc, cmpFunc)
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
        
    def setCmpFunc(self, cmp_func, filter_name='all'):
        """changes the comparing function, should that mean a resorting?"""
        if self.filtered_func.has_key(filter_name):
            self.filtered_func[1] = cmp_func
            self.sortData(filter=filter_name)
        
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
    
    def getCountOfSimilarPeers(self):
        count = 0
        for peer_data in self.data:
            if peer_data.get('similarity',None) is None:
                print "peer ",peer_data['content_name'],"has no similarity!!!!"
            if peer_data['similarity'] > 20:
                count = count + 1
        return count
    
    def getCountOfFriends(self):
        count = 0
        for peer_data in self.data:
            if peer_data['friend']:
                count = count + 1
        return count    
    
    def swap(self, array, index1, index2):
        aux = array[index1]
        array[index1] = array[index2]
        array[index2] = aux
        
    """cmpFunc(val1, val2) should return 1 if val1 > val2, 0 if val1 == val2, and -1 if val1 < val2"""
    def partition(self, array, left, right, pivotIndex, cmpFunc):
        pivotValue = array[pivotIndex]
        self.swap( array, pivotIndex, right) # Move pivot to end
        storeIndex = left
        for i in range(left,right):
            if cmpFunc(array[i], pivotValue) >= 0: #(orderMode=='descending' and array[i][key] >= pivotValue) or ( orderMode!='descending' and array[i][key] <= pivotValue):
                self.swap( array, storeIndex, i)
                storeIndex = storeIndex + 1
        self.swap( array, right, storeIndex) # Move pivot to its final place
        return storeIndex
    
    """cmpFunc(val1, val2) should return 1 if val1 > val2, 0 if val1 == val2, and -1 if val1 < val2"""
    def quicksort(self, array, left, right, cmpFunc):
        if right > left:
            #select a pivot index (e.g. pivotIndex = left)
            pivotIndex = left
            pivotNewIndex = self.partition(array, left, right, pivotIndex, cmpFunc)
            quicksort(array, left, pivotNewIndex-1, cmpFunc)
            quicksort(array, pivotNewIndex+1, right, cmpFunc)
     
    """cmpFunc(val1, val2) should return 1 if val1 > val2, 0 if val1 == val2, and -1 if val1 < val2"""
    def sortInPlace(self, list, cmpFunc):
        """apply a sorting algorithm without creating a new list"""
        self.quicksort(list, 0, len(list)-1, cmpFunc)
        
    def peerEqualFunc(peer1, peer2):
        if not peer1.has_key('permid') or not peer2.has_key('permid'):
            return False
        if peer1['permid'] == peer2['permid']:
            return True
        return False
        
    def insertInPlace(self, list, new_value, cmpFunc=None, equalFunc=peerEqualFunc):
        """iterate through the list to check two things: if the item is already in list
        and where it should be inserted based on the cmpFunc return value
        returns True if the list is changed, False otherwise
        see updateTopList for algorithm"""
        #check where to add the element, and also where is already inserted
        bChange = False
        index = 0
        llen = len(list)
        indexInsertAt = llen
        indexIsAt = -1
        while index < llen:
            if equalFunc(list[index],new_value):
                indexIsAt = index
            if cmpFunc is not None and cmpFunc(new_value,list[index])>0:
                indexInsertAt = index
            if indexIsAt != -1 and ( cmpFunc is None or indexInsertAt < llen ):
                break #both indexes are computed so no reason to continue
            index = index + 1
        if indexIsAt != -1:
            #update the content of the value
            old_value = list[indexIsAt]
            #update with data from new_value
            self.updatePeer(old_value, new_value)
            new_value = old_value
        if indexInsertAt != indexIsAt: #if on the same position, do nothing
            if indexIsAt != -1 and indexIsAt < llen-1 and equalFunc(new_value, list[indexIsAt+1]):
                return False #if is equal with the ones until insertion point, no need to do it
            old_value = None
            if indexIsAt != -1:
                #move from one position to another
                list.pop(indexIsAt)
                if indexIsAt < indexInsertAt:
                    indexInsertAt = indexInsertAt - 1
                bChange = True #there is a change in the list
#            if indexInsertAt < max_list_length: #don't insert an element that will be removed
            list.insert(indexInsertAt, new_value)
            bChange = True #there is a change in the list
        return bChange
    
    def getFilteredData(self, filter_name = 'all'):
        """returns a reference to the filtered data corresponding to the filter named as parameter
        it should check if data is really available (meaning prepareData was run)"""
        return self.filtered_data.get(filter_name,None)