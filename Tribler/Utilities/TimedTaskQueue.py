# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TimedTaskQueue is a server that executes tasks on behalf of e.g. the GUI that
# are too time consuming to be run by the actual GUI Thread (MainThread). Note 
# that you still need to delegate the actual updating of the GUI to the 
# MainThread via the wx.CallAfter mechanism.
#
import sys

from threading import Thread,Condition
from traceback import print_exc,print_stack
from time import time

DEBUG = False

class TimedTaskQueue:
    
    __single = None
    
    def __init__(self,nameprefix="TimedTaskQueue"):
        self.cond = Condition()
        self.queue = []
        self.thread = Thread(target = self.run)
        self.thread.setDaemon(True)
        self.thread.setName( nameprefix+self.thread.getName() )
        self.thread_started = False
        
    def register(self):
        if not self.thread_started:
            self.thread.start()
            self.thread_started = True
        
    def add_task(self,task,t):
        """ t parameter is now usable, unlike before """
        
        if task is None:
            print_stack()
        
        self.cond.acquire()
        when = time()+t
        if DEBUG:
            print >>sys.stderr,"ttqueue: ADD EVENT",t,task
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
                    print >>sys.stderr,"ttqueue: EVENT IN QUEUE",when,task
                now = time()
                if now < when:
                    # Event not due, wait some more
                    if DEBUG:
                        print >>sys.stderr,"ttqueue: EVENT NOT TILL",when-now
                    timeout = when-now
                    flag = True
                else:
                    # Event due, execute
                    if DEBUG:
                        print >>sys.stderr,"ttqueue: EVENT DUE"
                    self.queue.pop(0)
                    break
            self.cond.release()
            
            # Execute task outside lock
            try:
                task()        
            except:
                print_exc()
        
        
