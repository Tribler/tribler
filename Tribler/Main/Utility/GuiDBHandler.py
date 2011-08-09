#Written by Niels Zeilemaker
#Extending wx.lib.delayedresult with a startWorker method which uses single producer
#Additionally DelayedResult is returned, allowing a thread to wait for result

import wx
from wx.lib.delayedresult import SenderWxEvent, SenderCallAfter, AbortedException,\
    DelayedResult

import threading
from Queue import Queue
from threading import Event
from time import time
import sys
from traceback import format_stack, extract_stack, format_exc
import os

DEBUG = True

class GUIDBProducer(threading.Thread):
    # Code to make this a singleton
    __single = None
    
    def __init__(self):
        if GUIDBProducer.__single:
            raise RuntimeError, "GuiDBProducer is singleton"
        GUIDBProducer.__single = self
        threading.Thread.__init__(self, name = "GuiDBProducer")
        
        self.queue = Queue()
        self.setDaemon(True)

        self.start()
        
    def getInstance(*args, **kw):
        if GUIDBProducer.__single is None:
            GUIDBProducer(*args, **kw)       
        return GUIDBProducer.__single
    getInstance = staticmethod(getInstance)
    
    def Add(self, sender, workerFn, args=(), kwargs={},
            name=None, senderArg=None):
        """The sender will send the return value of 
        workerFn(*args, **kwargs) to the main thread. The name is 
        same as threading.Thread constructor parameters. 
        If sendReturn is False, then the return 
        value of workerFn() will not be sent. If senderArg is given, it 
        must be the name of the keyword arg to use to pass the sender into 
        the workerFn, so the function can send (typically many) results."""
        
        t1 = time()
        
        if senderArg:
            kwargs[senderArg] = sender
            
        def wrapper():
            try:
                #Set name of this thread to indicate which task is being processed
                if name:
                    self.setName("GuiDBProducer(%s)"%name)
                else:
                    self.setName("GuiDBProducer")
                
                t2 = time()
                result = workerFn(*args, **kwargs)
                
            except AbortedException:
                pass
            
            except Exception, exc:
                originalTb = format_exc() 
                extraInfo = self._extraInfo(exc)
                sender.sendException(exc, originalTb, extraInfo)
                
            else:
                sender.sendResult(result)
            
            t3 = time()
            
            if DEBUG:
                print >> sys.stderr, self.getName(),"Task took", t3 - t1, "to complete, actual task took", t3 - t2 
                    
        self.queue.put(wrapper)
        
    def _extraInfo(self, exception):
        """This method could be overridden in a derived class to provide 
        extra information when an exception is being sent instead of a 
        result. """
        return None
        
    def run(self):
        while True:
            task = self.queue.get()
            task()
            self.queue.task_done()

#Wrapping Senders for new delayedResult impl  
class MySender():
    def __init__(self, delayedResult, sendReturn):
        self.delayedResult = delayedResult
        self.sendReturn = sendReturn
    
    def sendResult(self, result):
        self.delayedResult.setResult(result)
        
        if self.sendReturn:
            self._sendImpl(self.delayedResult)
        
    def sendException(self, exception, originalTb, extraInfo = None):
        assert exception is not None
        self.delayedResult.setException(exception, originalTb, extraInfo)
        
        if self.sendReturn:
            self._sendImpl(self.delayedResult)
        else:
            #will cause exception to be raised
            self.delayedResult.get()
        
class MySenderWxEvent(MySender, SenderWxEvent):
    def __init__(self, handler, eventClass, delayedResult, resultAttr="delayedResult", jobID=None, sendReturn = True, **kwargs):
        SenderWxEvent.__init__(self, handler, eventClass, resultAttr, jobID, **kwargs)
        MySender.__init__(self, delayedResult, sendReturn)
        
class MySenderCallAfter(MySender, SenderCallAfter):
    def __init__(self, listener, delayedResult, jobID=None, args=(), kwargs={}, sendReturn = True):
        SenderCallAfter.__init__(self, listener, jobID, args, kwargs)
        MySender.__init__(self,  delayedResult, sendReturn)

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
        
    def setException(self, exception, original_traceback, extraInfo):
        self.__result = extraInfo
        self.__original_traceback = original_traceback
        self.__exception = exception
        
        self.isFinished.set()
    
    def get(self, timeout = None):
        if self.isFinished.wait(timeout):
            if self.__exception: # exception was raised!
                self.__exception.extraInfo = self.__result
                self.__exception.originalTraceback = self.__original_traceback
                print >> sys.stderr, self.__original_traceback 
                raise self.__exception
        
            return self.__result
    
    def wait(self, timeout = None):
        return self.isFinished.wait(timeout)
            
#Modified startWorker to use our single thread
#group and daemon variables have been removed 
def startWorker(
    consumer, workerFn, 
    cargs=(), ckwargs={}, 
    wargs=(), wkwargs={},
    jobID=None, delay=None,
    sendReturn=True, senderArg=None):
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
        sendReturn = False
        
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
        sender = MySenderWxEvent(consumer, eventClass, result, jobID=jobID, sendReturn = sendReturn, **ckwargs)
    else:
        sender = MySenderCallAfter(consumer, result, jobID, args=cargs, kwargs=ckwargs, sendReturn = sendReturn)
    
    thread = GUIDBProducer.getInstance()
    if delay:
        wx.CallLater(delay, thread.Add, sender, workerFn, wargs, wkwargs, 
                   jobID, senderArg)
    else:
        thread.Add(sender, workerFn, args=wargs, kwargs=wkwargs, 
                   name=jobID, senderArg=senderArg)

    return result 