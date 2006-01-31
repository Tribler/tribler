# Written by Jun Wang, Jie Yang
# see LICENSE.txt for license information

from copy import deepcopy
import random

class DictList:
    """ 
    List of dict. 
    All items should have the same data structure.
    It is NOT thread safe.
    """
    
    def __init__(self, max_size = 10000):
        self.max_size = max_size
        self.clean()
        
    def __len__(self):
        return len(self.data)

    def clean(self):
        self.data = []
        self.columns = []
        self.key = None
        self.order = 'increase'
        
    def printList(self):
        for i in range(len(self.data)):
            print i, ':', self.data[i]            

    def isFull(self):
        return len(self.data) >= self.max_size
        
    def length(self):
        return len(self.data)
        
    def filter(self, item, inplace=True):
        """ remove useless keys and add required keys in item """
        
        if not self.isValidItem(item):
            raise RuntimeError, "invalid type"
        if not inplace:
            item2 = deepcopy(item)
        else:
            item2 = item
        if self.columns:
            for key in item2.keys():
                if key not in self.columns:
                    item2.pop(key)
            for key in self.columns:
                if key not in item2:
                    item2[key] = None      
        if not inplace:
            return item2
                    
    def isValidItem(self, item):
        if not isinstance(item, dict):
            return False
        if self.key and (not item.has_key(self.key) or item[self.key] is None):
                return False
        return True          
        
    def importDictList(self, dict_list, columns, key=None, order ='increase'):
        """ 
        Import items from a dict list fill in the cache and 
        remove some items if the dict list is longer than max_size.
        It is deepcopy.
        Invalid items will be removed.
        """
        
        self.clean()
        self.columns = columns
        if key:
            if key not in columns:
                raise RuntimeError, "key is not in columns"
            self.key = key
            if order not in ('increase', 'decrease'):
                order = 'increase'
            self.order = order
        if not dict_list or len(dict_list) == 0:
            return
        # check if each item has the same structure
        self.data = dict_list[:]
        for item in self.data:
            self.filter(item)
        if key:
            invalid_items = []
            # remove any item which doesn't have the key
            for i in range(len(self.data)):
                if self.data[i][self.key] is None:
                    invalid_items.append(i)
                    print "Invalid item:", self.data[i], "doesn't have the key", self.key
            for i in invalid_items:
                self.data.pop(i)
            # sort items by key
            self.sortedby(self.key, order)
        if len(self.data) > self.max_size:
            self.data = self.data[:self.max_size]
        
    def sortedby(self, key, order ='increase', inplace=True):
        """ Return nothing if inplaced is True; else return sorted list """
        
        aux = [(self.data[i][key], i) for i in range(len(self.data))]
        aux.sort()
        if order == 'decrease':
            aux.reverse()
        result = [self.data[i] for junk, i in aux]
        if inplace: 
            self.data = result
        else:
            return result

    def findItem(self, key, value):
        for i in range(len(self.data)):
            if self.data[i][key] == value:
                return i
        return -1
        
    def updateItem(self, index, value):
        if self.data[index][self.key] != value[self.key]:
            self.data.pop(index)
            self.addItem(value)
        
    def addItem(self, item):
        """ 
        add one item.
        If it is ordered, new item will be inserted on a right place;
        Otherwise, new item will be inserted on the head. If the list is overflow,
        the last item will be removed.
        """
        
        self.filter(item)
        if not self.key:
            self.data.insert(0, item)
            idx = 0
        else:
            idx = self.findPlace(item)
            if idx < self.max_size:
                self.data.insert(idx, item)
        if len(self.data) > self.max_size:
            return idx, self.data.pop(self.max_size)
        else:
            return idx, None
        
    def findPlace(self, item):
        """ find place to insert in the ordered list by bisearch algorithm"""
        
        if not self.key:
            return 0
        value = item[self.key]
        low = 0
        high = len(self.data)
        if high == 0:
            return 0
        if self.order == 'increase':
            if value <= self.data[low]:
                return 0
            if value >= self.data[high-1]:
                if high < self.max_size:
                    return high
                else:
                    return self.max_size-1
            while low < high:
                mid = (low + high) / 2
                if value == self.data[mid][self.key]:
                    return mid
                elif value > self.data[mid][self.key]:
                    low = mid + 1
                else:
                    high = mid
            return low
        else:
            if value >= self.data[low]:
                return 0
            if value <= self.data[high-1]:
                if high < self.max_size:
                    return high
                else:
                    return self.max_size-1
            while low < high:
                mid = (low + high) / 2
                if value == self.data[mid][self.key]:
                    return mid
                elif value < self.data[mid][self.key]:
                    low = mid + 1
                else:
                    high = mid
            return low
    
#    def popItem(self, index):
#        return self.data.pop(index)
        
    def getItem(self, index):
        return self.data[index]
        
    def getItems(self, indexes):
        res = [self.data[i] for i in indexes]
        return res
        
    def getTopN(self, num):
        return self.data[:num]
        
    def getAll(self):
        return self.data[:]
        
    def getRandomItem(self):
        size = len(self.data)
        index = random.randint(0, size-1) # random int 0<=  <= size-1
        return self.data[index]
        
    def getRandomItems(self, num):
        size = len(self.data)
        if num > size:
            num = size
        population = range(size)
        index = random.sample(population, num)
        return self.getItems(index)
        
#    def setValue(self, index, key, value):
#        self.data[index][key] = value
#        
#    def setAllValues(self, key, value):
#        for item in self.data:
#            item[key] = value
#            
#    def getValue(self, index, key):
#        return self.data[index][key]
        
    def getAllValues(self, key):
        res = [item[key] for item in self.data]
        return res    
        
#    def getMinKey(self):
#        if len(self.data) == 0:
#            return 0
#        if not self.key or self.order == 'increase':
#            return self.data[0][self.key]
#        else:
#            return self.data[len(self.data)-1][self.key]
#            
#    def getMaxKey(self):
#        if len(self.data) == 0:
#            return 0
#        if not self.key or self.order == 'decrease':
#            return self.data[0][self.key]
#        else:
#            return self.data[len(self.data)-1][self.key]

if __name__ == "__main__":
    
    def test_load():
        d1 = DictList(5)
        preflist = []
        preflist.append({'ip':'1.1.1.1', 'created_time':2, 'name':'a'})
        preflist.append({'ip':'1.1.1.2', 'created_time':71, 'name':'b'})
        preflist.append({'ip':'1.1.1.3', 'created_time':4, 'name':'c'})
        preflist.append({'ip':'1.1.1.4', 'created_time':37, 'name':'d'})
        preflist.append({'ip':'1.1.1.5', 'created_time':53, 'name':'e'})
        preflist.append({'ip':'1.1.1.6', 'created_time':7, 'name':'f'})
        preflist.append({'ip':'1.1.1.7', 'created_time':99, 'name':'g'})
        preflist.append({'ip':'1.1.1.8', 'created_time':1, 'name':'h'})
        d1.importDictList(preflist, ['name', 'ip', 'created_time'], 'created_time', 'increase')
        item = {'ip':'1.1.1.9', 'created_time':40, 'name':'i'}
        d1.addItem(item)
        d1.printList()
        print d1.getRandomItems(2)
    
    test_load()