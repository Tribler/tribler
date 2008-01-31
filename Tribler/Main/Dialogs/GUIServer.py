# Written by Arno Bakker
# see LICENSE.txt for license information
#
# GUIServer is a server that executes tasks on behalf of the GUI that are too
# time consuming to be run by the actual GUI Thread (MainThread). Note that
# you still need to delegate the actual updating of the GUI to the MainThread via
# the wx.CallAfter() mechanism. 
#

from threading import Thread,Condition
from traceback import print_exc
from time import time

DEBUG = False

class GUIServer:
    
    __single = None
    
    def __init__(self):
        if GUIServer.__single:
            raise RuntimeError, "GUIServer is singleton"
        GUIServer.__single = self

        self.cond = Condition()
        self.queue = []
        self.thread = Thread(target = self.run)
        self.thread.setDaemon(True)
        self.thread.setName( "GUIServer"+self.thread.getName() )
        
    def getInstance(*args, **kw):
        if GUIServer.__single is None:
            GUIServer(*args, **kw)
        return GUIServer.__single
    getInstance = staticmethod(getInstance)

    def register(self):
        self.thread.setDaemon(True)
        self.thread.start()
        
    def resetSingleton(self): # for testing
        GUIServer.__single = None
        
    def add_task(self,task,t):
        """ t parameter is now usable, unlike before """
        self.cond.acquire()
        when = time()+t
        if DEBUG:
            print >>sys.stderr,"guiserv: ADD EVENT",t,task
        self.queue.append((when,task))
        self.cond.notify()
        self.cond.release()
        
    def run(self):
        """ Run by server thread """
        while True:
            task = None
            timeout = None
            flag = False
            self.cond.acquire()
            while True:
                while len(self.queue) == 0 or flag:
                    flag = False
                    if timeout is None:
                        # Wait until something is queued
                        self.cond.wait()
                    else:
                        # Wait till first event is due
                        self.cond.wait(timeout)
                # A new event was added or an event is due
                self.queue.sort()
                (when,task) = self.queue[0]
                if DEBUG:
                    print >>sys.stderr,"guiserv: EVENT IN QUEUE",when,task
                now = time()
                if now <= when:
                    # Event not due, wait some more
                    if DEBUG:
                        print >>sys.stderr,"guiserv: EVENT NOT TILL",when-now
                    timeout = when-now
                    flag = True
                else:
                    # Event due, execute
                    if DEBUG:
                        print >>sys.stderr,"guiserv: EVENT DUE"
                    self.queue.pop(0)
                    break
            self.cond.release()
            
            # Execute task outside lock
            try:
                task()        
            except:
                print_exc()
        
        
