# written by Yuan Yuan
# see LICENSE.txt for license information

from threading import Lock
from traceback import print_exc, print_stack
import sys

class BasicObserver:
    def register(self):
        pass
    
    def unregister(self):
        pass
    
    def update(self):
        pass

class DBObserver(BasicObserver):
    __single = None
    
    def getInstance(*args, **kw):
        if DBObserver.__single is None:
            DBObserver(*args, **kw)       
        return DBObserver.__single
    getInstance = staticmethod(getInstance)
    
    def __init__(self):
        if DBObserver.__single:
            raise RuntimeError, "DBObserver is singleton"
        DBObserver.__single = self
        self.dict_FunList = {}
        self.lock = Lock()
        
    def register(self, fun, key="default"):
        self.lock.acquire()
        try:
            self.dict_FunList[key].index(fun)
            # if no exception, fun already exist!
            print >> sys.stderr, "dbobserver: DBObserver register error. " + str(fun.__name__) + " already exist!"
            self.lock.release()
            return
        except KeyError:
            self.dict_FunList[key] = []
            self.dict_FunList[key].append(fun)
        except ValueError:
            self.dict_FunList[key].append(fun)
        except Exception, msg:
            print >> sys.stderr, "dbobserver: DBObserver register error. " + str(fun), Exception, msg
            print_exc(file=sys.stderr)
        self.lock.release()
        
    def unregister(self, fun, key = "default"):
        self.lock.acquire()
        if not self.dict_FunList.has_key(key):
            return
        self.dict_FunList[key].remove(fun)
        self.lock.release()
        
    def update(self, key, *paramenter):
        self.lock.acquire()
        try:
            for fun in self.dict_FunList.get(key, []): # call all functions for a certain key
                fun(*paramenter)     # lock is used to avoid dead lock
        except Exception, msg:
            print >> sys.stderr, "dbobserver: DBObserver update error. ", Exception, msg
            print_exc(file=sys.stderr)
                       
        self.lock.release()
    