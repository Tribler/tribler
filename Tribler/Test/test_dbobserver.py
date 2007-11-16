from Tribler.Core.CacheDB.DBObserver import *

def fun1(parameter, lock):
    print "in fun1"
    
def fun2(parameter, lock):
    print "in fun2"
    
def fun3(parameter, lock):
    print "in fun3, parameter: " + str(parameter)
    s, ob = parameter
    ob.update("view", "VIEW", lock)
    
def fun4(parameter, lock):
    print "in fun4, paramter: " + parameter

if __name__ == "__main__":
    ob = DBObserver.getInstance()
    ob.register(fun1, "test")
    ob.register(fun2, "test")
    ob.register(fun3, "test")
    
    ob.register(fun2, "test")
    ob.unregister(fun2, "test")
    ob.unregister(fun2, "test")
    ob.register(fun2, "test")
    
    ob.register(fun4, "view")
    
    
    ob.update("test", ("this is the key", ob))