# data stored in list: self[:]
# data structure:
#       self:[0][1]...[-1]
#            oldder...newer
#       sort: lower... higher
#

import random, traceback, thread,time
from copy import deepcopy


class DictListQueue(list):
    def __init__(self, cacheMaxSize= 10000):
        self.cacheSize = 0  #len(init_cache)
        self.cacheMaxSize = cacheMaxSize
        self.order = 'increase'
        self.key = None
        self.columns = []
        #self.lock = thread.allocate_lock()
        self.lock = False
        self.isAccessing = False
        random.seed(time.time())
        
        
    def acquireAccess(self):
        # wait until isAccess is False
        while self.isAccessing == True:
            time.sleep(0.01)
        # has the right to access
        self.isAcessing = True
        

    def releaseAccess(self):
        # finish the work set it to False
        self.isAccessing = False
        
    def importer(self, dictList):
        # import a dictList; adjust cachesize and cacheMaxSize to fit the dictList
        
        if not isinstance(dictList, list) or not isinstance(dictList[0], dict):
            raise RuntimeError, "impoter only accepts a list of dictionaries"
        
        self.cacheSize = len(dictList)
        self[:] = dictList[:]
        self.cacheMaxSize = self.cacheSize
        
    def importN(self, dictList, columns=[], key=None, order ='increase'):
        """ import items from a dict list fill in the cache and 
            remove some items if the dict list is longer than cacheMaxSize 
        """
        
        if len(dictList) == 0:
            return
        keys = dictList[0].keys()
        if not columns:
            columns = keys
        else:
            for column in columns:
                if column not in keys:
                    raise RuntimeError, "The columns don't match the list"
        self.columns = columns
        if key not in self.columns:
            raise RuntimeError, "The key is not in columns"
        self.key = key
                
        if not isinstance(dictList, list) or len(dictList) == 0 \
            or not isinstance(dictList[0], dict):
            return
            
        SelectedDictList = []
        for item in dictList:
            selectedDict = {}
            for column in self.columns:
                selectedDict.update({column:item[column]})
            SelectedDictList.append(selectedDict)
            
        self.extend(SelectedDictList)
        if isinstance(key, str):
            method= 'overwrite'
            self.sortedby(key, method, order)
        newSize = len(self)
        removedItems = []
        if self.cacheMaxSize < newSize:
            removeSize = newSize - self.cacheMaxSize
            removedItems = self[:removeSize]
            self.removeN(removeSize)
            self.cacheSize = self.cacheMaxSize
        else:
            self.cacheSize = newSize
        return removedItems
            
    def _shift(self):
        return
    def resetCacheSize(self):
        return
    
    def _enqueue(self, obj):
        self.append(obj)
        
    def _dequeue(self):
        if len(self) > 0:
            return self.pop(0)
        else:
            return 'null'

    def _print(self):
        """for debug purpose"""
        print str(self)

    def getCacheSize(self):
        #while self.lock == True:
        #    pass
        return len(self)

    #def add(self,obj):
    #    return self._lock('add',obj)

    def add(self, objOrigin):
        """insert an obj (in our case:Dict) into list
        the last record in list may be removed if the cacheSize
        is out of cacheMaxSize
        """
        #self.lock.acquire()
        self.acquireAccess()
        obj = objOrigin.copy()
        self.cacheSize = self.getCacheSize()
        self.lock = True
        if self.cacheSize < self.cacheMaxSize:
            self._enqueue(obj)
            self.cacheSize += 1
        else:
            self._enqueue(obj)
            self._dequeue()
        self.lock = False
        #self.lock.release()
        self.releaseAccess()
        return self.cacheSize

    def remove(self):
        """first came first out"""
        #self.lock.acquire()
        self.cacheSize = self.getCacheSize()
        if self.cacheSize > 0:
            self._dequeue()
            self.cacheSize -= 1
            #self.lock.release()
            return self.cacheSize
        else:
            #self.lock.release()
            return 'null'
        
    def removeN(self, num):
        """first came first out"""
        
        self.cacheSize = self.getCacheSize()
        if num > self.cacheSize:
            num = self.cacheSize
        for i in range(num):
           size =  self.remove()
        return size

    def getAll(self):
        all = deepcopy(self[:])
        return all
        
    def getTopN(self, num):
        top = deepcopy(self[-1*num:])
        return top

    def printAll(self):
        """print on sceen"""
        print self

    def printList(self):
        size = self.getCacheSize()
        for i in range(size):
            print 'index:', i, 'obj:', self[i]
 
    def getARecord(self,index):
        """get a record implemented by Dict"""
        index = int(index)
        self.cacheSize = self.getCacheSize()
        if (index >= self.cacheSize)| (index < 0):
            return 'null'
        popSize = self.getCacheSize()
        try:
            return self[index]
        except:
            print 'something wroing in getARecord@DictListQueue.py', 'index', index, 'cacheSize', self.cacheSize
            return 'null'

    def getRecords(self, indexs):
        """get a set of records"""
        #self.lock.acquire()
        a=[]
        for i in indexs:
            a.append(self[i])
        #self.lock.release()
        return a

    def getLength(self):
        return self.cacheSize

    def getMaxCacheSize(self):
        return self.cacheMaxSize

    def getMaxSize(self):
        return self.cacheMaxSize

    def getCurSize(self):
        return self.cacheSize

    def getPeer(self,index):
        return self.getARecord(index)

    def getPeers(self,indexs):
        return self.getRecords(indexs)

    def getRandomPeer(self):
        size = self.getCacheSize()
        index = random.randint(0, size-1) # random int 0<=  <= size-1
        return self.getPeer(index)
        
    def getRandomPeers(self,num):
        size = self.getCacheSize()
        if num > size:
            num = size
        population = range(size)
        index = random.sample(population,num)
        return self.getPeers(index)

    def getSampledPeer(self,ranking):
        self.acquireAccess()
        peers  = self.getAll()  # get a copy of list not dict
        rankAccum = 0
        for peer in peers:
            rankAccum = rankAccum + peer[ranking]
            peer[ranking]=rankAccum
        randVar = random.random()*rankAccum
        prePeerRank = 0
        for peer in peers:
            if prePeerRank < randVar and peer[ranking] >= randVar:
                break
        self.releaseAccess()
        return peer
    
    def sortedby(self, key, method='overwrite', order ='increase'):
        """
        in an increase order: higher value is in a higher index.
        index=0 is the smallest one: default
        """
        self.acquireAccess()
        #self.lock.acquire()
        #orignial sort algrithm
        if False:
            self.order = order
            self.key = key
            print 'current key', self.key 
            if method == 'overwrite':
                peers = self
            else:
                peers = self[:]
            peers.sort(self._compare)
            self.releaseAccess()
            #self.lock.release()
            return peers
        else:
            #new one
            try:
                sort = Sorter()
                sort(self,key)
            except:
                print "-----------------------------------------"
                traceback.print_exc()
                print 'error in sorting:', self
                print "-----------------------------------------"
            #self.lock.release()
            self.releaseAccess()
            return self

    def find(self,key,value):
        #self.lock.acquire()
        self.acquireAccess()
        self.cacheSize = self.getCacheSize()
        if self.cacheSize == 0:
            #self.lock.release()
            self.acquireAccess()
            return [-1,'']
        result =[-1,'']
        try:
            for a in range(self.getCacheSize()): #print a, self[a]
                a = int(a)
            #    print 'compare:', self[a][key], 'to', value
                if self[a][key]== value:
                    result[0]= a
                    result[1]= self[a]
                    break
        except:
            print 'key:', key, type(key), 'index',a,'cacheSize', self.cacheSize,'listsize:', len(self),'lists:', self 
        #print result
        #self.lock.release()
        self.releaseAccess()
        return result
    
    def _compare(self,x,y):
        print type(self)
        print x, y
        if self.key  and x.has_key(self.key) and y.has_key(self.key):
            #print type(x),type(self.index),y[self.index]
            if self.order == 'increase':
               # print 'increase'
                return cmp(x[self.key],y[self.key])
            else :
               # print 'decrease'
                return cmp(y[self.key],x[self.key])
        else:
            print 'need define index key first!', x, y

class Sorter:
    def _helper(self, data, aux, inplace):
        aux.sort( )
        result = [data[i] for junk, i in aux]
        if inplace: data[:] = result
        return result

    def byItem(self, data, itemindex=None, inplace=1):
        if itemindex is None:
            if inplace:
                data.sort( )
                result = data
            else:
                result = data[:]
                result.sort( )
                return result
        else:
            #aux = [(data[i][itemindex], i) for i in range(len(data))]
            aux = [(data[i][itemindex], i) for i in range(data.getCacheSize())]
            return self._helper(data, aux, inplace)
            # a couple of handy synonyms
    sort = byItem
    __call__ = byItem

    def byAttribute(self, data, attributename, inplace=1):
        #aux = [(getattr(data[i],attributename),i) for i in range(len(data))]
        aux = [(getattr(data[i],attributename),i) for i in range(data.getCacheSize())]
       
        return self._helper(data, aux, inplace)
            
def testPeerCache():
    a = DictListQueue(cacheMaxSize = 5)
    print a.add({'ip':'1.1.1.1','peer_id':2})
    print a.add({'ip':'1.1.1.2','peer_id':8})
    print a.add({'ip':'1.1.1.3','peer_id':7})
    print a.add({'ip':'1.1.1.4','peer_id':5})
    print a.add({'ip':'1.1.1.5','peer_id':180})
    print a.add({'ip':'1.1.1.6','peer_id':3})
    print a.add({'ip':'1.1.1.7','peer_id':4})
    print 'all the data'
    a._print()
    a.remove()
    print a.add({'ip':'1.1.1.9','peer_id':13})
    print a.add({'ip':'1.1.1.8','peer_id':12})
    print 'remove one add two, all the data' 
    a._print()
    print 'sorted by ip'
    #a.sortedby('ip')
    a._shift()
    sort = Sorter()
    sort(a,'ip')
    print 'we are done the sort'
    a.printAll()
    print 'sorted by peerid'
    a.sortedby('peer_id')
    a.printAll() 
    result = a.find('peer_id',180)
    print 'find peerid 6 at', result[0], result[1]
    a.remove()
    a.printAll()
    print a.getPeer(a.cacheSize-1)
    a.sortedby('peer_id')
    a.printList()
    return 

def testCacheSize():
    a = DictListQueue(cacheMaxSize = 5)
    print 'initial', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.1','peer_id':2})
    print 'add one', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.2','peer_id':8})
    print 'add two', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.3','peer_id':7})
    print 'add three', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize
    
    print a.add({'ip':'1.1.1.4','peer_id':5})
    print 'add four', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.5','peer_id':180})
    print 'add five', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.6','peer_id':3})
    print 'add six', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.add({'ip':'1.1.1.7','peer_id':4})
    print 'add 7', 'cacheSize', a.cacheSize, 'cacheMaxSize', a.cacheMaxSize

    print a.remove()

    print a.remove()

    print a.remove()

    print a
    
def testImportN():
    
    a = DictListQueue(cacheMaxSize = 5)
    preflist = []
    preflist.append({'ip':'1.1.1.1', 'created_time':2})
    preflist.append({'ip':'1.1.1.2', 'created_time':71})
    preflist.append({'ip':'1.1.1.3', 'created_time':4})
    preflist.append({'ip':'1.1.1.4', 'created_time':37})
    preflist.append({'ip':'1.1.1.5', 'created_time':53})
    preflist.append({'ip':'1.1.1.6', 'created_time':7})
    preflist.append({'ip':'1.1.1.7', 'created_time':99})
    preflist.append({'ip':'1.1.1.8', 'created_time':1})
    print a.importN(preflist, [], 'created_time')
    a.printList()
    print
    preflist = []
    preflist.append({'ip1':'1.1.1.1', 'created_time':2})
    preflist.append({'ip1':'1.1.1.2', 'created_time':71})
    preflist.append({'ip1':'1.1.1.3', 'created_time':4})
    preflist.append({'ip1':'1.1.1.4', 'created_time':37})
    preflist.append({'ip1':'1.1.1.5', 'created_time':53})
    preflist.append({'ip1':'1.1.1.6', 'created_time':7})
    preflist.append({'ip1':'1.1.1.7', 'created_time':99})
    preflist.append({'ip1':'1.1.1.8', 'created_time':1})
    print a.importN(preflist, [], 'created_time')
    a.printList()

if '__main__'== __name__:
    #testCacheSize()
    #testPeerCache()
    testImportN()
    
                                                                                        


