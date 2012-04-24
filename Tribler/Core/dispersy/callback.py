# Python 2.5 features
from __future__ import with_statement

"""
A callback thread running Dispersy.
"""

from dprint import dprint
from heapq import heappush, heappop
from itertools import chain
from thread import get_ident
from threading import Thread, Lock, Event
from time import sleep, time
from types import GeneratorType, TupleType

if __debug__:
    from itertools import islice
    from atexit import register as atexit_register
    # dprint warning when registered call, or generator call, takes more than N seconds
    CALL_DELAY_FOR_WARNING = 0.5
    # dprint warning when registered call, or generator call, should have run N seconds ago
    QUEUE_DELAY_FOR_WARNING = 1.0

class Callback(object):
    def __init__(self):
        # _event is used to wakeup the thread when new actions arrive
        self._event = Event()
        self._event_set = self._event.set
        self._event_is_set = self._event.is_set

        # _lock is used to protect variables that are written to on multiple threads
        self._lock = Lock()

        # _thread_ident is used to detect when methods are called from the same thread
        self._thread_ident = 0

        # _state contains the current state of the thread.  it is protected by _lock and follows the
        # following states:
        #
        #                                              --> fatal-exception -> STATE_EXCEPTION
        #                                             /
        # STATE_INIT -> start() -> PLEASE_RUN -> STATE_RUNNING
        #                                \            \
        #                                 --------------> stop() -> PLEASE_STOP -> STATE_FINISHED
        #
        self._state = "STATE_INIT"
        if __debug__: dprint("STATE_INIT")

        # _exception is set to SystemExit, KeyboardInterrupt, GeneratorExit, or AssertionError when
        # any of the registered callbacks raises any of these exceptions.  in this case _state will
        # be set to STATE_EXCEPTION.  it is protected by _lock
        self._exception = None

        # _exception_handlers contains a list with callable functions of methods.  all handlers are
        # called whenever an exception occurs.  first parameter is the exception, second parameter
        # is a boolean indicating if the exception is fatal (i.e. True indicates SystemExit,
        # KeyboardInterrupt, GeneratorExit, or AssertionError)
        self._exception_handlers = []

        # _id contains a running counter to ensure that every scheduled callback has its own unique
        # identifier.  it is protected by _lock
        self._id = 0

        # requests are ordered by deadline and moved to -expired- when they need to be handled
        # (deadline, priority, root_id, (call, args, kargs), callback)
        self._requests = []

        # expired requests are ordered and handled by priority
        # (priority, root_id, None, (call, args, kargs), callback)
        self._expired = []

        if __debug__:
            def must_close(callback):
                assert callback.is_finished
            atexit_register(must_close, self)
            self._debug_statistics = {}

    @property
    def is_running(self):
        """
        Returns True when the state is STATE_RUNNING.
        """
        return self._state == "STATE_RUNNING"

    @property
    def is_finished(self):
        """
        Returns True when the state is either STATE_FINISHED or STATE_EXCEPTION.  In either case the
        thread is no longer running.
        """
        return self._state == "STATE_FINISHED" or self._state == "STATE_EXCEPTION"

    @property
    def exception(self):
        """
        Returns the exception that caused the thread to exit when when any of the registered callbacks
        raises either SystemExit, KeyboardInterrupt, GeneratorExit, or AssertionError.
        """
        return self._exception

    def attach_exception_handler(self, func):
        """
        Attach a new exception notifier.

        FUNC will be called whenever a registered call raises an exception.  The first parameter
        will be the raised exception, the second parameter will be a boolean indicating if the
        exception was fatal.

        Fatal exceptions are SystemExit, KeyboardInterrupt, GeneratorExit, or AssertionError.  These
        exceptions will cause the Callback thread to exit.  The Callback thread will continue to
        function on all other exceptions.
        """
        assert callable(func), "handler must be callable"
        with self._lock:
            assert not func in self._exception_handlers, "handler was already attached"
            self._exception_handlers.append(func)

    def detach_exception_handler(self, func):
        """
        Detach an existing exception notifier.
        """
        assert callable(func), "handler must be callable"
        with self._lock:
            assert func in self._exception_handlers, "handler is not attached"
            self._exception_handlers.remove(func)

    def _call_exception_handlers(self, exception, fatal):
        with self._lock:
            exception_handlers = self._exception_handlers[:]
        for exception_handler in exception_handlers:
            try:
                exception_handler(exception, fatal)
            except Exception:
                dprint(exception=True, level="error")
                assert False, "the exception handler should not cause an exception"

    def register(self, call, args=(), kargs=None, delay=0.0, priority=0, id_="", callback=None, callback_args=(), callback_kargs=None):
        """
        Register CALL to be called.

        The call will be made with ARGS and KARGS as arguments and keyword arguments, respectively.
        ARGS must be a tuple and KARGS must be a dictionary.

        CALL may return a generator object that will be repeatedly called until it raises the
        StopIteration exception.  The generator can yield floating point values to reschedule the
        generator after that amount of seconds counted from the scheduled start of the call.  It is
        possible to yield other values, however, these are currently undocumented.

        The call will be made after DELAY seconds.  DELAY must be a floating point value.

        When multiple calls should be, or should have been made, the PRIORITY will decide the order
        at which the calls are made.  Calls with a higher PRIORITY will be handled before calls with
        a lower PRIORITY.  PRIORITY must be an integer.  The default PRIORITY is 0.  The order will
        be undefined for calls with the same PRIORITY.

        Each call is identified with an ID_.  A unique numerical identifier will be assigned when no
        ID_ is specified.  And specified id's must be (unicode)strings.  Registering multiple calls
        with the same ID_ is allowed, all calls will be handled normally, however, all these calls
        will be removed if the associated ID_ is unregistered.

        Once the call is performed the optional CALLBACK is registered to be called immediately.
        The first parameter of the CALLBACK will always be either the returned value or the raised
        exception.  If CALLBACK_ARGS is given it will be appended to the first argument.  If
        CALLBACK_KARGS is given it is added to the callback as keyword arguments.

        Returns ID_ if specified or a uniquely generated numerical identifier

        Example:
         > callback.register(my_func, delay=10.0)
         > -> my_func() will be called after 10.0 seconds

        Example:
         > def my_generator():
         >    while True:
         >       print "foo"
         >       yield 1.0
         > callback.register(my_generator)
         > -> my_generator will be called immediately printing "foo", subsequently "foo" will be
              printed at 1.0 second intervals
        """
        assert callable(call), "CALL must be callable"
        assert isinstance(args, tuple), "ARGS has invalid type: %s" % type(args)
        assert kargs is None or isinstance(kargs, dict), "KARGS has invalid type: %s" % type(kargs)
        assert isinstance(delay, float), "DELAY has invalid type: %s" % type(delay)
        assert isinstance(priority, int), "PRIORITY has invalid type: %s" % type(priority)
        assert isinstance(id_, basestring), "ID_ has invalid type: %s" % type(id_)
        assert callback is None or callable(callback), "CALLBACK must be None or callable"
        assert isinstance(callback_args, tuple), "CALLBACK_ARGS has invalid type: %s" % type(callback_args)
        assert callback_kargs is None or isinstance(callback_kargs, dict), "CALLBACK_KARGS has invalid type: %s" % type(callback_kargs)
        if __debug__: dprint("register ", call, " after ", delay, " seconds")

        with self._lock:
            if not id_:
                self._id += 1
                id_ = self._id

                if delay <= 0.0:
                    heappush(self._expired,
                             (-priority,
                              id_,
                              None,
                              (call, args, {} if kargs is None else kargs),
                              None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

                else:
                    heappush(self._requests,
                             (delay + time(),
                              -priority,
                              id_,
                              (call, args, {} if kargs is None else kargs),
                              None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

            # wakeup if sleeping
            if not self._event_is_set():
                self._event_set()
            return id_

    def persistent_register(self, id_, call, args=(), kargs=None, delay=0.0, priority=0, callback=None, callback_args=(), callback_kargs=None):
        """
        Register CALL to be called only if ID_ has not already been registered.

        Aside from the different behavior of ID_, all parameters behave as in register(...).

        Example:
         > callback.persistent_register("my-id", my_func, ("first",), delay=60.0)
         > callback.persistent_register("my-id", my_func, ("second",))
         > -> my_func("first") will be called after 60 seconds, my_func("second") will not be called at all

        Example:
         > callback.register(my_func, ("first",), delay=60.0, id_="my-id")
         > callback.persistent_register("my-id", my_func, ("second",))
         > -> my_func("first") will be called after 60 seconds, my_func("second") will not be called at all
        """
        assert isinstance(id_, basestring), "ID_ has invalid type: %s" % type(id_)
        assert id_, "ID_ may not be an empty (unicode)string"
        assert callable(call), "CALL must be callable"
        assert isinstance(args, tuple), "ARGS has invalid type: %s" % type(args)
        assert kargs is None or isinstance(kargs, dict), "KARGS has invalid type: %s" % type(kargs)
        assert isinstance(delay, float), "DELAY has invalid type: %s" % type(delay)
        assert isinstance(priority, int), "PRIORITY has invalid type: %s" % type(priority)
        assert callback is None or callable(callback), "CALLBACK must be None or callable"
        assert isinstance(callback_args, tuple), "CALLBACK_ARGS has invalid type: %s" % type(callback_args)
        assert callback_kargs is None or isinstance(callback_kargs, dict), "CALLBACK_KARGS has invalid type: %s" % type(callback_kargs)
        if __debug__: dprint("persistent register ", call, " after ", delay, " seconds")

        with self._lock:
            for tup in self._requests:
                if tup[2] == id_:
                    break

            else:
                # not found in requests
                for tup in self._expired:
                    if tup[1] == id_:
                        break

                else:
                    # not found in expired
                    if delay <= 0.0:
                        heappush(self._expired,
                                 (-priority,
                                  id_,
                                  None,
                                  (call, args, {} if kargs is None else kargs),
                                  None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

                    else:
                        heappush(self._requests,
                                 (delay + time(),
                                  -priority,
                                  id_,
                                  (call, args, {} if kargs is None else kargs),
                                  None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

                    # wakeup if sleeping
                    if not self._event_is_set():
                        self._event_set()

            return id_

    def replace_register(self, id_, call, args=(), kargs=None, delay=0.0, priority=0, callback=None, callback_args=(), callback_kargs=None):
        """
        Replace (if present) the currently registered call ID_ with CALL.

        This is a faster way to handle an unregister and register call.  All parameters behave as in
        register(...).
        """
        assert isinstance(id_, (basestring, int)), "ID_ has invalid type: %s" % type(id_)
        assert id_, "ID_ may not be zero or an empty (unicode)string"
        assert callable(call), "CALL must be callable"
        assert isinstance(args, tuple), "ARGS has invalid type: %s" % type(args)
        assert kargs is None or isinstance(kargs, dict), "KARGS has invalid type: %s" % type(kargs)
        assert isinstance(delay, float), "DELAY has invalid type: %s" % type(delay)
        assert isinstance(priority, int), "PRIORITY has invalid type: %s" % type(priority)
        assert callback is None or callable(callback), "CALLBACK must be None or callable"
        assert isinstance(callback_args, tuple), "CALLBACK_ARGS has invalid type: %s" % type(callback_args)
        assert callback_kargs is None or isinstance(callback_kargs, dict), "CALLBACK_KARGS has invalid type: %s" % type(callback_kargs)
        if __debug__: dprint("replace register ", call, " after ", delay, " seconds")
        with self._lock:
            # un-register
            for index in reversed([index for index, tup in enumerate(self._requests) if tup[2] == id_]):
                del self._requests[index]
            for index in reversed([index for index, tup in enumerate(self._expired) if tup[1] == id_]):
                del self._expired[index]

            # register
            if delay <= 0.0:
                heappush(self._expired,
                         (-priority,
                          id_,
                          None,
                          (call, args, {} if kargs is None else kargs),
                          None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

            else:
                heappush(self._requests,
                         (delay + time(),
                          -priority,
                          id_,
                          (call, args, {} if kargs is None else kargs),
                          None if callback is None else (callback, callback_args, {} if callback_kargs is None else callback_kargs)))

            # wakeup if sleeping
            if not self._event_is_set():
                self._event_set()
            return id_

    def unregister(self, id_):
        """
        Unregister a callback using the ID_ obtained from the register(...) method
        """
        assert isinstance(id_, (basestring, int)), "ROOT_ID has invalid type: %s" % type(id_)
        assert id_, "ID_ may not be zero or an empty (unicode)string"
        if __debug__: dprint(id_)
        with self._lock:
            # un-register
            for index in reversed([index for index, tup in enumerate(self._requests) if tup[2] == id_]):
                del self._requests[index]
            for index in reversed([index for index, tup in enumerate(self._expired) if tup[1] == id_]):
                del self._expired[index]

    def call(self, call, args=(), kargs=None, delay=0.0, priority=0, id_="", timeout=0.0, default=None):
        """
        Register a blocking CALL to be made, waits for the call to finish, and returns or raises the
        result.

        TIMEOUT gives the maximum amount of time to wait before un-registering CALL.  No timeout
        will occur when TIMEOUT is 0.0.  When a timeout occurs the DEFAULT value is returned.

        DEFAULT can be anything.  The DEFAULT value is returned when a TIMEOUT occurs.  When DEFAULT
        is an Exception instance it will be raised instead of returned.

        For the arguments CALL, ARGS, KARGS, DELAY, PRIORITY, and ID_: see the register(...) method.
        """
        assert isinstance(timeout, float)
        assert 0.0 <= timeout
        def callback(result):
            container[0] = result
            event.set()

        # result container
        container = [default]
        event = Event()

        # register the call
        id_ = self.register(call, args, kargs, delay, priority, id_, callback)

        # wait for call to finish
        event.wait(None if timeout == 0.0 else timeout)

        if isinstance(container[0], Exception):
            raise container[0]
        else:
            return container[0]

    def start(self, name="Generic-Callback", wait=True):
        """
        Start the asynchronous thread.

        Creates a new thread and calls the _loop() method.
        """
        assert self._state == "STATE_INIT", "Already (done) running"
        assert isinstance(name, str)
        assert isinstance(wait, bool), "WAIT has invalid type: %s" % type(wait)
        if __debug__: dprint()
        with self._lock:
            self._state = "STATE_PLEASE_RUN"
            if __debug__: dprint("STATE_PLEASE_RUN")

        thread = Thread(target=self._loop, name=name)
        thread.daemon = True
        thread.start()

        if wait:
            # Wait until the thread has started
            while self._state == "STATE_PLEASE_RUN":
                sleep(0.01)

        return self.is_running

    def stop(self, timeout=10.0, wait=True, exception=None):
        """
        Stop the asynchronous thread.

        When called with wait=True on the same thread we will return immediately.
        """
        assert isinstance(timeout, float)
        assert isinstance(wait, bool)
        if __debug__: dprint()
        if self._state == "STATE_RUNNING":
            with self._lock:
                if exception:
                    self._exception = exception
                self._state = "STATE_PLEASE_STOP"
                if __debug__: dprint("STATE_PLEASE_STOP")

                # wakeup if sleeping
                self._event.set()

            if wait and not self._thread_ident == get_ident():
                while self._state == "STATE_PLEASE_STOP" and timeout > 0.0:
                    sleep(0.01)
                    timeout -= 0.01

                if __debug__:
                    if timeout <= 0.0:
                        dprint("timeout.  perhaps callback.stop() was called on the same thread?")

        return self.is_finished

    def _loop(self):
        if __debug__: dprint()

        # put some often used methods and object in the local namespace
        actual_time = 0
        event_clear = self._event.clear
        event_wait = self._event.wait
        event_is_set = self._event.is_set
        expired = self._expired
        get_timestamp = time
        lock = self._lock
        requests = self._requests

        self._thread_ident = get_ident()

        with lock:
            if self._state == "STATE_PLEASE_RUN":
                self._state = "STATE_RUNNING"
                if __debug__: dprint("STATE_RUNNING")

        while 1:
            actual_time = get_timestamp()

            with lock:
                # check if we should continue to run
                if self._state != "STATE_RUNNING":
                    break

                # move expired requests from REQUESTS to EXPIRED
                while requests and requests[0][0] <= actual_time:
                    # notice that the deadline and priority entries are switched, hence, the entries in
                    # the EXPIRED list are ordered by priority instead of deadline
                    _, priority, root_id, call, callback = heappop(requests)
                    heappush(expired, (priority, root_id, None, call, callback))

                if expired:
                    # we need to handle the next call in line
                    priority, root_id, _, call, callback = heappop(expired)
                    wait = 0.0

                else:
                    # there is nothing to handle
                    wait = min(300.0, requests[0][0] - actual_time if requests else 300.0)

                if event_is_set():
                    event_clear()

            if wait:
                if __debug__: dprint("wait at most %.1fs before next call" % wait)
                event_wait(wait)

            else:
                if __debug__:
                    # 10/02/12 Boudewijn: in python 2.5 generators do not have .__name__
                    debug_call_name = call[0].__name__ if isinstance(call, TupleType) else str(call)
                    debug_call_start = time()

                # call can be either:
                # 1. a generator
                # 2. a (callable, args, kargs) tuple

                try:
                    if isinstance(call, TupleType):
                        # callback
                        if __debug__:
                            debug_begin = get_timestamp()
                        result = call[0](*call[1], **call[2])
                        if isinstance(result, GeneratorType):
                            # we only received the generator, no actual call has been made to the
                            # function yet, therefore we call it again immediately
                            call = result

                        elif callback:
                            with lock:
                                heappush(expired, (priority, root_id, None, (callback[0], (result,) + callback[1], callback[2]), None))

                    if isinstance(call, GeneratorType):
                        # start next generator iteration
                        if __debug__:
                            debug_begin = get_timestamp()
                        result = call.next()
                        assert isinstance(result, float), type(result)
                        assert result >= 0.0
                        with lock:
                            heappush(requests, (get_timestamp() + result, priority, root_id, call, callback))

                except StopIteration:
                    if callback:
                        with lock:
                            heappush(expired, (priority, root_id, None, (callback[0], (result,) + callback[1], callback[2]), None))

                except (SystemExit, KeyboardInterrupt, GeneratorExit, AssertionError), exception:
                    dprint(exception=True, level="error")
                    with lock:
                        self._state = "STATE_EXCEPTION"
                        self._exception = exception
                    self._call_exception_handlers(exception, True)

                except Exception, exception:
                    dprint(exception=True, level="error")
                    if callback:
                        with lock:
                            heappush(expired, (priority, root_id, None, (callback[0], (exception,) + callback[1], callback[2]), None))
                    self._call_exception_handlers(exception, False)

                if __debug__:
                    if debug_call_name not in self._debug_statistics:
                        self._debug_statistics[debug_call_name] = [0.0, 0]

                    self._debug_statistics[debug_call_name][0] += time() - debug_call_start
                    self._debug_statistics[debug_call_name][1] += 1

        with lock:
            requests = requests[:]
            expired = expired[:]

        # send GeneratorExit exceptions to remaining generators
        for _, _, _, call, _ in chain(expired, requests):
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

        if __debug__:
            dprint("top ten calls, sorted by cumulative time", line=True)
            key = lambda (_, (cumulative_time, __)): cumulative_time
            for call_name, (cumulative_time, call_count) in islice(sorted(self._debug_statistics.iteritems(), key=key, reverse=True), 10):
                dprint("%8.2fs %6dx" % (cumulative_time, call_count), "  - ", call_name)

            dprint("top ten calls, sorted by execution count", line=True)
            key = lambda (_, (__, call_count)): call_count
            for call_name, (cumulative_time, call_count) in islice(sorted(self._debug_statistics.iteritems(), key=key, reverse=True), 10):
                dprint("%8.2fs %6dx" % (cumulative_time, call_count), "  - ", call_name)

if __debug__:
    def main():
        c = Callback()
        c.start()
        d = Callback()
        d.start()

        def call1():
            dprint(time())

        sleep(2)
        dprint(time())
        c.register(call1, delay=1.0)

        sleep(2)
        dprint(line=1)

        def call2():
            delay = 3.0
            for i in range(10):
                dprint(time(), " ", i)
                sleep(delay)
                if delay > 0.0:
                    delay -= 1.0
                yield 1.0
        c.register(call2)
        sleep(11)
        dprint(line=1)

        def call3():
            delay = 3.0
            for i in range(10):
                dprint(time(), " ", i)
                yield Switch(d)
                # perform code on Callback d
                sleep(delay)
                if delay > 0.0:
                    delay -= 1.0

                yield Switch(c)
                # perform code on Callback c
        c.register(call3)
        sleep(11.0)
        dprint(line=1)

        # CPU intensive call... should 'back off'
        def call4():
            for _ in xrange(10):
                sleep(2.0)
                desync = (yield 1.0)
                dprint("desync... ", desync)
                while desync > 0.1:
                    dprint("backing off... ", desync)
                    desync = (yield desync)
                    dprint("next try... ", desync)
        dprint(line=1)

        def call5_bussy():
            for _ in xrange(10):
                desync = yield 0.0
                dprint("on bussy (", desync, ")", force=1)
                sleep(0.4)
        def call5_idle():
            for _ in xrange(10):
                desync = yield Idle()
                dprint("on idle (", desync, ")", force=1)
        c.register(call5_bussy)
        c.register(call5_idle)
        dprint(line=1)

        def call6():
            dprint("before", force=1)
            yield Idle(5.0)
            dprint("after", force=1)
        c.register(call6)

        def call7():
            dprint("init", force=1)
            while True:
                yield 1.0
                dprint("-", force=1)
                c.unregister(task_id)
        task_id = c.register(call7)
        c.unregister(task_id)

        sleep(21.0)
        dprint(line=1)

        d.stop()
        c.stop()

    if __name__ == "__main__":
        main()
