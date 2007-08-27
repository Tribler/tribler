import sys
import copy, threading
from Tribler import Web2
from Tribler.Web2.util.observer import Observer

class DataOnDemand:
    
    def __init__(self, sort=lambda x:x):
        self.data = []
        self.datalock = threading.RLock()
        self.updateFuns = []
        self.requested = 0
        self.sort = sort
        self.filters = []

    def isDod(self):
        return True

    def register(self, updateFun):
        if self.updateFuns.count(updateFun) == 0:
            self.updateFuns.append(updateFun)

    def unregister(self, updateFun):
        try:
            self.updateFuns.remove(updateFun)
        except:
            print 'web2.unregister() unnecessary'

    def notify(self, item=None):
        for fun in self.updateFuns:
            fun(item) #????

    def _addItem(self, item):
        for filter in self.filters:
            if not filter(item):
                print 'item got filtered'
                return False

        self.data.append(item)
        #print "WEB2: datachanged: " + str(self.data)
        return True

    def addItem(self, item):
        print "web2.addItem"
        self.datalock.acquire()
        if self._addItem(item):
            self.data = self.sort(self.data)
            print 'web2.addItem: notify'
            self.notify(item)
        self.datalock.release()

    def addItems(self, items):
        #print "web2.addItems"
        self.datalock.acquire()
#        for item in items:
#            self._addItem(item)
#        self.data = self.sort(self.data)
#        self.notify()
        # Quickfix: do not sort anymore. Otherwise it conflicts with incoming remotesearch
        for item in items:
            self.addItem(item)
        self.datalock.release()

    def numRequested(self):
        return self.requested

    def getData(self):
        return copy.copy(self.data)

    def setSort(self, sort):
        self.datalock.acquire()
        self.sort = sort
        self.data = self.sort(self.data)
        self.notify()
        self.datalock.release()

    def addFilter(self, filter):
        self.filters.append(filter)

    def remFilter(self, filter):
        self.filters.remove(filter)

    def filterData(self):
        pass


class DataOnDemandWeb2(DataOnDemand, Observer):

    def __init__(self, query, type='video', sort=lambda x:x):
        #print >>sys.stderr,"DataOnDemandWeb2: query is",query
        DataOnDemand.__init__(self, sort)
        Observer.__init__(self)
        self.web2querylock = threading.RLock()
        self.web2query = Web2.web2query(query, type)
        self.web2query.attach(self)
        self.web2query.start()
        self.end = False

    def request(self, num):
        if self.end:
            return

        self.web2querylock.acquire()
        
        if self.requested >= num:
            self.web2querylock.release() # Arno: forgot to unlock?
            return
        
        more = num - self.requested
        self.requestMore(more)

        self.web2querylock.release()


    def requestMore(self, num):
        if self.end:
            return

        self.web2querylock.acquire()

        self.web2query.getMore(num)
        self.requested += num

        #print 'WEB2.0: requested:', num

        self.web2querylock.release()


    def update(self, subject, m):
        #print "WEB2.0: new item received"
        if m == None:
            print 'web2: item was none'
            self.end = True
        else:
            self.addItem(m)

    def stop(self):
        self.web2querylock.acquire()
        if self.web2query:
            self.web2query.detach(self)
            self.web2query.quit()
            self.web2query = None

        self.web2querylock.release()


