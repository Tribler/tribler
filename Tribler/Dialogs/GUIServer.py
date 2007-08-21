# Written by Arno Bakker
# see LICENSE.txt for license information
#
# GUIServer is a server that executes tasks on behalf of the GUI that are too
# time consuming to be run by the actual GUI Thread (MainThread). Note that
# you still need to delegate the actual updating of the GUI to the MainThread via
# the invokeLater() mechanism. See safeguiupdate.py
#

from threading import Thread,Condition
from traceback import print_exc

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
        """ t parameter currently ignored """
        self.cond.acquire()
        self.queue.append(task)
        self.cond.notify()
        self.cond.release()
        
    def run(self):
        """ Run by server thread """
        while True:
            task = None
            self.cond.acquire()
            while len(self.queue) == 0:
                self.cond.wait()
            task = self.queue.pop(0)
            self.cond.release()
            
            # Execute task outside lock
            try:
                task()        
            except:
                print_exc()
        
        
