#Written by Niels Zeilemaker
#Extending wx.lib.delayedresult with a startWorker method which uses single producer
#Additionally DelayedResult is returned, allowing a thread to wait for result

import wx
from wx.lib.delayedresult import SenderWxEvent, SenderCallAfter, AbortedException,\
    DelayedResult

import threading
from Queue import Queue
from threading import Event
from thread import get_ident
from time import time
import sys
from traceback import format_stack, extract_stack, format_exc, print_exc,\
    print_stack
import os

DEBUG = False

class GUIDBProducer():
    # Code to make this a singleton
    __single = None
    
    def __init__(self):
        if GUIDBProducer.__single:
            raise RuntimeError, "GuiDBProducer is singleton"
        GUIDBProducer.__single = self
        
        #Let get the reference to the shared database_thread
        from Tribler.Core.Session import Session

        session = Session.get_instance()
        triblerlaunchmany = session.lm
        self.database_thread = triblerlaunchmany.database_thread
        
    def getInstance(*args, **kw):
        if GUIDBProducer.__single is None:
            GUIDBProducer(*args, **kw)       
        return GUIDBProducer.__single
    getInstance = staticmethod(getInstance)
    
    def onSameThread(self):
        return get_ident() == self.database_thread._thread_ident
    
    def Add(self, sender, workerFn, args=(), kwargs={}, name=None, delay = 0.0):
        """The sender will send the return value of 
        workerFn(*args, **kwargs) to the main thread. The name is 
        same as threading.Thread constructor parameters. 
        If sendReturn is False, then the returnvalue of workerFn() will not be sent. """
        
        t1 = time()
        def wrapper():
            try:
                t2 = time()
                result = workerFn(*args, **kwargs)
                
            except AbortedException:
                pass
            
            except Exception, exc:
                originalTb = format_exc() 
                sender.sendException(exc, originalTb)
                
            else:
                sender.sendResult(result)
            t3 = time()
            
            if DEBUG:
                print >> sys.stderr, "Task(%s) took %.1f to complete, actual task took %.1f"%(name, t3 - t1, t3 - t2)
        
        if not self.onSameThread():
            self.database_thread.register(wrapper, delay=delay, id_=name)
            
        else:
            print >> sys.stderr, "Task(%s) scheduled for thread on same thread, executing immediately"%name
            wrapper()
        
#Wrapping Senders for new delayedResult impl  
class MySender():
    def __init__(self, delayedResult):
        self.delayedResult = delayedResult
    
    def sendResult(self, result):
        self.delayedResult.setResult(result)
        self._sendImpl(self.delayedResult)
        
    def sendException(self, exception, originalTb):
        assert exception is not None
        self.delayedResult.setException(exception, originalTb)
        self._sendImpl(self.delayedResult)
        
class MySenderWxEvent(MySender, SenderWxEvent):
    def __init__(self, handler, eventClass, delayedResult, resultAttr="delayedResult", jobID=None, **kwargs):
        SenderWxEvent.__init__(self, handler, eventClass, resultAttr, jobID, **kwargs)
        MySender.__init__(self, delayedResult)
        
class MySenderCallAfter(MySender, SenderCallAfter):
    def __init__(self, listener, delayedResult, jobID=None, args=(), kwargs={}):
        SenderCallAfter.__init__(self, listener, jobID, args, kwargs)
        MySender.__init__(self,  delayedResult)

#ASyncDelayedResult, allows a get call before result is set
#This call is blocking, but allows you to specify a timeout
class ASyncDelayedResult():
    def __init__(self, jobID=None):
        self.__result = None
        self.__exception = None
        self.__jobID = jobID
        
        self.isFinished = Event()
        
    def setResult(self, result):
        self.__result = result
        
        self.isFinished.set()
        
    def setException(self, exception, original_traceback):
        self.__original_traceback = original_traceback
        self.__exception = exception
        
        self.isFinished.set()
    
    def get(self, timeout = 100):
        if self.isFinished.wait(timeout):
            if self.__exception: # exception was raised!
                self.__exception.originalTraceback = self.__original_traceback
                raise self.__exception
            return self.__result
        
        else:
            print_stack()
            print >> sys.stderr, "TIMEOUT on get", self.__jobID
            
    def wait(self, timeout = None):
        return self.isFinished.wait(timeout)

def exceptionConsumer(delayedResult, *args, **kwargs):
    try:
        delayedResult.get()
    except Exception, e:
        print >> sys.stderr, e.originalTraceback
        
#Modified startWorker to use our single thread
#group and daemon variables have been removed 
def startWorker(
    consumer, workerFn, 
    cargs=(), ckwargs={}, 
    wargs=(), wkwargs={},
    jobID=None, delay=0.0):
    """
    Convenience function to send data produced by workerFn(*wargs, **wkwargs) 
    running in separate thread, to a consumer(*cargs, **ckwargs) running in
    the main thread. This function merely creates a SenderCallAfter (or a
    SenderWxEvent, if consumer derives from wx.EvtHandler), and a Producer,
    and returns immediately after starting the Producer thread. The jobID
    is used for the Sender and as name for the Producer thread. Returns the 
    delayedResult created, in case caller needs join/etc.
    """
    
    if not consumer:
        consumer = exceptionConsumer
        
    if jobID is None:
        try:
            filename, line, function, text = extract_stack(limit = 2)[0]
            _, filename = os.path.split(filename)
            jobID = "%s:%s (%s)"%(filename, line, function) 
        except:
            pass 
        
    result = ASyncDelayedResult(jobID)
    
    if isinstance(consumer, wx.EvtHandler):
        eventClass = cargs[0]
        sender = MySenderWxEvent(consumer, eventClass, result, jobID=jobID, **ckwargs)
    else:
        sender = MySenderCallAfter(consumer, result, jobID, args=cargs, kwargs=ckwargs)
    
    thread = GUIDBProducer.getInstance()
    thread.Add(sender, workerFn, args=wargs, kwargs=wkwargs, 
                name=jobID, delay=delay)

    return result

def onWorkerThread():
    dbProducer = GUIDBProducer.getInstance()
    return dbProducer.onSameThread()

