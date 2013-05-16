# Written by Niels Zeilemaker
# Extending wx.lib.delayedresult with a startWorker method which uses single producer
# Additionally DelayedResult is returned, allowing a thread to wait for result

import wx
from wx.lib.delayedresult import SenderWxEvent, SenderCallAfter, AbortedException, \
    DelayedResult, SenderNoWx

import threading
from collections import namedtuple
from Queue import Queue
from threading import Event, Lock, RLock
from thread import get_ident
from time import time
import sys
from traceback import format_stack, extract_stack, format_exc, print_exc, \
    print_stack
import os
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from inspect import isgeneratorfunction
from random import randint

# Arno, 2012-07-18: Priority for real user visible GUI tasks (e.g. list update)
GUI_PRI_DISPERSY = 99
DEFAULT_PRI_DISPERSY = 0

DEBUG = False

class GUIDBProducer():
    # Code to make this a singleton
    __single = None
    __singleton_lock = RLock()

    def __init__(self, database_thread):
        if GUIDBProducer.__single:
            raise RuntimeError, "GuiDBProducer is singleton"

        self.database_thread = database_thread
        self.guitaskqueue = GUITaskQueue.getInstance()

        # Lets get a reference to utility
        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
        if GUIUtility.hasInstance():
            self.utility = GUIUtility.getInstance().utility
        else:
            Utility = namedtuple('Utility', ['abcquitting', ])
            self.utility = Utility(False)

        self.uIds = set()
        self.uIdsLock = Lock()

        self.nrCallbacks = {}

    @classmethod
    def getInstance(cls, *args, **kw):
        with cls.__singleton_lock:
            if GUIDBProducer.__single is None:
                GUIDBProducer.__single = GUIDBProducer(*args, **kw)
        return GUIDBProducer.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        GUIDBProducer.__single = None

    def onSameThread(self, type):
        onDBThread = get_ident() == self.database_thread._thread_ident
        if type == "dbThread" or onDBThread:
            return onDBThread

        return threading.currentThread().getName().startswith('GUITaskQueue')

    def Add(self, sender, workerFn, args=(), kwargs={}, name=None, delay=0.0, uId=None, retryOnBusy=False, priority=0, workerType="dbthread"):
        """The sender will send the return value of
        workerFn(*args, **kwargs) to the main thread.
        """
        if self.utility.abcquitting:
            if DEBUG:
                print >> sys.stderr, "GUIDBHandler: abcquitting ignoring Task(%s)" % name
            return

        assert uId is None or isinstance(uId, unicode), type(uId)
        assert name is None or isinstance(name, unicode), type(name)

        if uId:
            try:
                self.uIdsLock.acquire()
                if uId in self.uIds:
                    if DEBUG:
                        print >> sys.stderr, "GUIDBHandler: Task(%s) already scheduled in queue, ignoring uId = %s" % (name, uId)
                    return
                else:
                    self.uIds.add(uId)
            finally:
                self.uIdsLock.release()

            callbackId = uId
        else:
            callbackId = name

        if DEBUG:
            print >> sys.stderr, "GUIDBHandler: adding Task(%s)" % callbackId

        if __debug__:
            self.uIdsLock.acquire()
            self.nrCallbacks[callbackId] = self.nrCallbacks.get(callbackId, 0) + 1
            if self.nrCallbacks[callbackId] > 10:
                print >> sys.stderr, "GUIDBHandler: Scheduled Task(%s) %d times" % (callbackId, self.nrCallbacks[callbackId])

            self.uIdsLock.release()

        t1 = time()
        def wrapper():
            if __debug__:
                self.uIdsLock.acquire()
                self.nrCallbacks[callbackId] = self.nrCallbacks.get(callbackId, 0) - 1
                self.uIdsLock.release()

            try:
                t2 = time()
                result = workerFn(*args, **kwargs)

            except (AbortedException, wx.PyDeadObjectError):
                return

            except Exception, exc:
                if str(exc).startswith("BusyError") and retryOnBusy:
                    print >> sys.stderr, "GUIDBHandler: BusyError, retrying Task(%s) in 0.5s" % name
                    self.database_thread.register(wrapper, delay=0.5, id_=name)

                    return

                originalTb = format_exc()
                sender.sendException(exc, originalTb)
                return

            t3 = time()
            if DEBUG:
                print >> sys.stderr, "GUIDBHandler: Task(%s) took to be called %.1f (expected %.1f), actual task took %.1f %s" % (name, t2 - t1, delay, t3 - t2, workerType)

            if uId:
                try:
                    self.uIdsLock.acquire()
                    if uId in self.uIds:
                        self.uIds.discard(uId)

                    # this callback has been removed during wrapper, cancel now
                    else:
                        return
                finally:
                    self.uIdsLock.release()

            # if we get to this step, send result to callback
            try:
                sender.sendResult(result)
            except:
                print_exc()
                print >> sys.stderr, "GUIDBHandler: Could not send result of Task(%s)" % name

        wrapper.__name__ = str(name)

        if not self.onSameThread(workerType) or delay:
            if workerType == "dbThread":
                if not self.database_thread.is_running:
                    self.getDatabaseThread()

                if isgeneratorfunction(workerFn):
                    self.database_thread.register(workerFn, delay=delay, priority=priority, id_=callbackId)
                else:
                    self.database_thread.register(wrapper, delay=delay, priority=priority, id_=callbackId)

            elif workerType == "guiTaskQueue":
                self.guitaskqueue.add_task(wrapper, t=delay)
        else:
            if __debug__:
                print >> sys.stderr, "GUIDBHandler: Task(%s) scheduled for thread on same thread, executing immediately" % name
            wrapper()

    def Remove(self, uId):
        if uId in self.uIds:
            if DEBUG:
                print >> sys.stderr, "GUIDBHandler: removing Task(%s)" % uId

            try:
                self.uIdsLock.acquire()
                self.uIds.discard(uId)

                if __debug__:
                    self.nrCallbacks[uId] = self.nrCallbacks.get(uId, 0) - 1

            finally:
                self.uIdsLock.release()

            self.database_thread.unregister(uId)
            self.guitaskqueue.remove_task(uId)

# Wrapping Senders for new delayedResult impl
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
        MySender.__init__(self, delayedResult)

class MySenderNoWx(MySender, SenderNoWx):
    def __init__(self, listener, delayedResult, jobID=None, args=(), kwargs={}):
        SenderNoWx.__init__(self, listener, jobID, args, kwargs)
        MySender.__init__(self, delayedResult)

# ASyncDelayedResult, allows a get call before result is set
# This call is blocking, but allows you to specify a timeout
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

    def get(self, timeout=100):
        if self.wait(timeout):
            if self.__exception:  # exception was raised!
                self.__exception.originalTraceback = self.__original_traceback
                print >> sys.stderr, self.__original_traceback
                raise self.__exception

            return self.__result
        else:
            print_stack()
            print >> sys.stderr, "TIMEOUT on get", self.__jobID, timeout

    def wait(self, timeout=None):
        return self.isFinished.wait(timeout) or self.isFinished.isSet()

def exceptionConsumer(delayedResult, *args, **kwargs):
    try:
        delayedResult.get()
    except Exception, e:
        print >> sys.stderr, e.originalTraceback

# Modified startWorker to use our single thread
# group and daemon variables have been removed
def startWorker(
    consumer, workerFn,
    cargs=(), ckwargs={},
    wargs=(), wkwargs={},
    jobID=None, delay=0.0,
    uId=None, retryOnBusy=False,
    priority=DEFAULT_PRI_DISPERSY, workerType="dbThread"):
    """
    Convenience function to send data produced by workerFn(*wargs, **wkwargs)
    running in separate thread, to a consumer(*cargs, **ckwargs) running in
    the main thread. This function merely creates a SenderCallAfter (or a
    SenderWxEvent, if consumer derives from wx.EvtHandler), and a Producer,
    and returns immediately after starting the Producer thread. The jobID
    is used for the Sender and as name for the Producer thread. The uId is
    used to check if such a task is already scheduled, ignores it if it is.
    Returns the delayedResult created, in case caller needs join/etc.
    """
    if isgeneratorfunction(workerFn):
        assert consumer == None, "Cannot have consumer and yielding task"
        consumer = None

    if not consumer:
        consumer = exceptionConsumer

    if not workerFn:
        raise Exception("no workerfunction specified")

    if jobID is None:
        if __debug__:
            try:
                filename, line, function, text = extract_stack(limit=2)[0]
                _, filename = os.path.split(filename)
                jobID = u"%s:%s (%s)" % (filename, line, function)
            except:
                pass
        else:
            jobID = unicode(randint(1, 10000000))

    result = ASyncDelayedResult(jobID)
    app = wx.GetApp()
    if not app:
        sender = MySenderNoWx(consumer, result, jobID, args=cargs, kwargs=ckwargs)
    elif isinstance(consumer, wx.EvtHandler):
        eventClass = cargs[0]
        sender = MySenderWxEvent(consumer, eventClass, result, jobID=jobID, **ckwargs)
    else:
        sender = MySenderCallAfter(consumer, result, jobID, args=cargs, kwargs=ckwargs)

    thread = GUIDBProducer.getInstance()
    thread.Add(sender, workerFn, args=wargs, kwargs=wkwargs,
            name=jobID, delay=delay, uId=uId, retryOnBusy=retryOnBusy, priority=priority, workerType=workerType)

    return result

def cancelWorker(uId):
    thread = GUIDBProducer.getInstance()
    thread.Remove(uId)

def onWorkerThread(type):
    dbProducer = GUIDBProducer.getInstance()
    return dbProducer.onSameThread(type)
