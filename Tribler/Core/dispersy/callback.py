# Python 2.5 features
from __future__ import with_statement

"""
A callback thread running Dispersy.
"""

from heapq import heappush, heappop
from threading import Thread, Lock, Event
from time import sleep, time
from types import GeneratorType
from dprint import dprint

if __debug__:
    import atexit

class Callback(object):
    def __init__(self):
        self._event = Event()
        self._lock = Lock()
        self._state = "STATE_INIT"
        if __debug__: dprint("STATE_INIT")
        self._id = 0
        self._timestamp = time()
        self._new_actions = []  # (type, action)
                                # type=register, action=(deadline, priority, root_id, (call, args, kargs))
                                # type=unregister, action=root_id

        if __debug__:
            def must_close(callback):
                assert callback._state == "STATE_FINISHED"
            atexit.register(must_close, self)

    @property
    def is_running(self):
        return self._state == "STATE_RUNNING"

    @property
    def is_finished(self):
        return self._state == "STATE_FINISHED"

    def add_task(self, func, delay=0.0):
        import sys
        import traceback
        print >> sys.stderr, "Depricated: Callback.add_task(FUNC, DELAY).  Use Callback.register(FUNC, delay=DELAY) instead"
        traceback.print_stack()
        assert isinstance(delay, (int, float))
        return self.register(func, delay=float(delay))

    def register(self, call, args=(), kargs=None, delay=0.0, priority=0, id_=""):
        assert hasattr(call, "__call__"), "CALL must be callable"
        assert isinstance(args, tuple), "ARGS has invalid type: %s" % type(args)
        assert kargs is None or isinstance(kargs, dict), "KARGS has invalid type: %s" % type(kargs)
        assert isinstance(delay, float), "DELAY has invalid type: %s" % type(delay)
        assert isinstance(priority, int), "PRIORITY has invalid type: %s" % type(priority)
        assert isinstance(id_, str), "ID_ has invalid type: %s" % type(id_)
        if __debug__: dprint("after ", delay, " seconds call ", call)
        if kargs is None:
            kargs = {}
        with self._lock:
            if not id_:
                self._id += 1
                id_ = self._id
            self._new_actions.append(("register", (self._timestamp + delay, 512 - priority, id_, (call, args, kargs))))
            # wakeup if sleeping
            self._event.set()
            return id_

    def unregister(self, root_id):
        """
        Unregister a callback using the ROOT_ID obtained from the register(...) method
        """
        assert isinstance(root_id, (str, int)), "ROOT_ID has invalid type: %s" % type(root_id)
        if __debug__: dprint(root_id)
        with self._lock:
            self._new_actions.append(("unregister", root_id))

    def start(self, name="Generic-Callback", wait=True):
        """
        Start the asynchronous thread.

        Creates a new thread and calls the _loop() method.
        """
        assert self._state == "STATE_INIT", "Already (done) running"
        assert isinstance(name, str)
        assert isinstance(wait, bool), "WAIT has invalid type: %s" % type(wait)
        if __debug__: dprint()
        thread = Thread(target=self._loop, name=name)
        thread.daemon = True
        thread.start()

        if wait:
            # Wait until the thread has started
            while self._state == "STATE_INIT":
                sleep(0.01)

    def stop(self, timeout=10.0, wait=True):
        """
        Stop the asynchronous thread.
        """
        if __debug__: dprint()
        if self._state == "STATE_RUNNING":
            with self._lock:
                self._state = "STATE_PLEASE_STOP"
                if __debug__: dprint("STATE_PLEASE_STOP")

            if wait:
                while self._state == "STATE_PLEASE_STOP" and timeout >= 0.0:
                    sleep(0.01)
                    timeout -= 0.01

        return self._state == "STATE_FINISHED"

    def _loop(self):
        if __debug__: dprint()

        # put some often used methods and object in the local namespace
        get_timestamp = time
        lock = self._lock
        new_actions = self._new_actions

        # the timestamp that the callback is currently handling
        actual_time = 0
        # requests are ordered by deadline and moved to -expired- when they need to be handled
        requests = [] # (deadline, priority, root_id, (call, args, kargs))
        # expired requests are ordered and handled by priority
        expired = [] # (priority, deadline, root_id, (call, args, kargs))

        with lock:
            assert self._state == "STATE_INIT"
            self._state = "STATE_RUNNING"
            if __debug__: dprint("STATE_RUNNING")

        while True:
            actual_time = get_timestamp()

            with lock:
                # todo: what is faster (1) extend list and sort or (2)
                # heappuch every item

                # schedule all new actions
                for type_, action in new_actions:
                    if type_ == "register":
                        heappush(requests, action)
                    else:
                        assert type_ == "unregister"
                        requests = [request for request in requests if not request[2] == action]
                        expired = [request for request in expired if not request[1] == action]
                del new_actions[:]
                self._event.clear()

                # make sure that we should still be running
                if self._state != "STATE_RUNNING":
                    break

                # move expired requests from REQUESTS to EXPIRED
                while requests and requests[0][0] <= actual_time:
                    deadline, priority, root_id, call = heappop(requests)
                    expired.append((priority, deadline, root_id, call))

                # self._timestamp tells us where the thread -should- be.  it is either ACTUAL_TIME
                # or the deadline-timestamp of the request we are handling.  this distinction is
                # essential to schedule events consistently.
                if expired:
                    self._timestamp = expired[0][1]
                else:
                    self._timestamp = actual_time

            if expired:
                # we need to handle the next call in line
                priority, deadline, root_id, call = expired.pop(0)

                while True:
                    # call can be either:
                    # 1. A generator
                    # 2. A (callable, args, kargs) tuple

                    if isinstance(call, GeneratorType):
                        try:
                            # start next generator iteration
                            if __debug__: dprint("sync: %.4fs" % (get_timestamp() - deadline), " when calling ", call)
                            result = call.next()
                        except StopIteration:
                            pass
                        except:
                            dprint(exception=True, level="error")
                            if __debug__:
                                self.stop()
                        else:
                            # schedule CALL again in RESULT seconds
                            assert isinstance(result, float)
                            assert result >= 0.0
                            heappush(requests, (deadline + result, priority, root_id, call))

                    else:
                        try:
                            # callback
                            if __debug__: dprint("sync: %.4fs" % (get_timestamp() - deadline), " when calling ", call[0])
                            result = call[0](*call[1], **call[2])
                        except:
                            dprint(exception=True, level="error")
                            if __debug__:
                                self.stop()
                        else:
                            if isinstance(result, GeneratorType):
                                # we only received the generator, no actual call has been made to the
                                # function yet, therefore we call it again immediately
                                call = result
                                continue

                    # break out of the while loop
                    break

            else:
                # we need to wait for new requests
                if requests:
                    # there are no requests that have to be handled right now. Sleep for a while.
                    if __debug__: dprint("wait: %.4fs" % (requests[0][0] - actual_time))
                    self._event.wait(min(300.0, requests[0][0] - actual_time))

                else:
                    # there are no requests on the list, wait till something is scheduled
                    if __debug__: dprint("wait: 300.0s")
                    self._event.wait(300.0)
                continue

        # send GeneratorExit exceptions to remaining generators
        for _, _, _, call in expired + requests:
            if isinstance(call, GeneratorType):
                if __debug__: dprint("raise Shutdown in ", call)
                try:
                    call.close()
                except:
                    dprint(exception=True, level="error")

        # set state to finished
        with lock:
            if __debug__: dprint("STATE_FINISHED")
            self._state = "STATE_FINISHED"
