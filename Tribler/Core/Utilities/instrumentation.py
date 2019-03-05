"""
instrumentation.

Author(s): Elric Milon
"""
from __future__ import print_function

import threading
from decorator import decorator
from os import sys
from threading import Lock, RLock, Thread
from time import sleep, time

MAX_SAME_STACK_TIME = 60


@decorator
def synchronized(wrapped, instance, *args, **kwargs):
    if instance is None:
        owner = wrapped
    else:
        owner = instance

    lock = vars(owner).get('_synchronized_lock', None)

    if lock is None:
        meta_lock = vars(synchronized).setdefault(
            '_synchronized_meta_lock', Lock())

        with meta_lock:
            lock = vars(owner).get('_synchronized_lock', None)

            if lock is None:
                lock = RLock()
                setattr(owner, '_synchronized_lock', lock)

    with lock:
        return wrapped(instance, *args, **kwargs)


class WatchDog(Thread):

    """
    Watchdog thread, will periodically check if all registered events are set and
    clear them.  If any if them is still cleared on the next iteration, a big fat
    warning will be printed along with some debug info to help debugging the
    issue.
    """

    def __init__(self):
        super(WatchDog, self).__init__()
        self.setDaemon(True)
        self.setName(self.__class__.__name__)
        self.debug = False
        self._registered_events = {}
        self.check_for_deadlocks = False

        self.max_same_stack_time = MAX_SAME_STACK_TIME

        self.should_stop = False
        self.deadlock_found = False
        self.stacks = {}
        self.event_timestamps = {}
        self.event_timeouts = {}
        self.tripped_canaries = []
        self.times = {}

    @synchronized
    def _reset_state(self):
        self.should_stop = False
        self.deadlock_found = False
        self.stacks = {}
        self.event_timestamps = {}
        self.tripped_canaries = []
        self.times = {}

    def start(self, *argv, **kwargs):
        self._reset_state()
        return super(WatchDog, self).start(*argv, **kwargs)

    def join(self, *argv, **kwargs):
        if self.debug:
            self.printe("Stopping watchdog")
        self.should_stop = True
        super(WatchDog, self).join(*argv, **kwargs)
        if self.debug:
            self.printe("Watchdog stopped")

    @synchronized
    def register_event(self, event, name, timeout=10):
        self.event_timeouts[name] = timeout
        self.event_timestamps[name] = time()
        self._registered_events[name] = event

    @synchronized
    def unregister_event(self, name):
        self.event_timeouts.pop(name, None)
        self.event_timestamps.pop(name, None)
        self._registered_events.pop(name, None)

    def printe(self, line):
            print(line, file=sys.stderr)

    def run(self):
        events_to_unregister = []
        while not self.should_stop:
            sleep(0.2)
            with self._synchronized_lock:
                if self.check_for_deadlocks:
                    self.look_for_deadlocks()
                for name, event in self._registered_events.items():
                    if event.is_set():
                        event.clear()
                        self.event_timestamps[name] = time()
                        if self.debug:
                            self.printe("watchog %s is OK" % name)
                    elif (self.event_timestamps[name] + self.event_timeouts[name]) < time():
                        self.printe("watchog %s *******TRIPPED!******, hasn't been set for %.4f secs." % (
                            name, time() - self.event_timestamps[name]))
                        self.printe("disabling it and printing traces for all threads.:")
                        events_to_unregister.append(name)
                        self.print_all_stacks()
                while events_to_unregister:
                    name = events_to_unregister.pop()
                    if self.debug:
                        self.printe(">>>>>>>>> UNREGISTERING %r" % name)
                    self.tripped_canaries.append(name)
                    self.unregister_event(name)
        if self.debug:
            self.printe(">>>>>>>>> I SHOULD STOP")

    def get_thread_name(self, thread_id):
        for thread in threading.enumerate():
            if thread.ident == thread_id:
                return thread.name
        return "Unknown"

    @staticmethod
    def repr_(value):
        try:
            return repr(value)
        except:
            return "<Error while REPRing value>"

    def print_all_stacks(self):
        self.printe("\n*** STACKTRACE - START ***\n")

        for thread_id, frame in sys._current_frames().items():
            self.printe("\n### ThreadID: %s Thread name: %s" % (thread_id, self.get_thread_name(thread_id)))

            self.printe("Locals by frame, innermost last:")
            while frame:
                self.printe("%s:%s %s:" % (frame.f_code.co_filename,
                                           frame.f_lineno, frame.f_code.co_name))
                for key, value in frame.f_locals.items():
                    value = WatchDog.repr_(value)
                    if len(value) > 500:
                        value = value[:500] + "..."
                        self.printe("| %12s = %s" % (key, value))
                frame = frame.f_back

        self.printe("\n*** STACKTRACE - END ***\n")

    def get_threads_info(self):
        """
        Return information about available threads.
        """
        threads = []
        for thread_id, frame in sys._current_frames().items():

            frame_list = []
            while frame:
                frame_str = "%s:%s %s:\n" % (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)
                for key, value in frame.f_locals.items():
                    value = WatchDog.repr_(value)
                    if len(value) > 500:
                        value = value[:500] + "..."
                        frame_str += "| %12s = %s" % (key, value)
                frame = frame.f_back
                frame_list.append(frame_str.rstrip())

            threads.append({
                'thread_id': thread_id,
                'thread_name': self.get_thread_name(thread_id),
                'frames': frame_list
            })
        return threads

    def look_for_deadlocks(self):
        for thread_id, stack in sys._current_frames().items():
            if thread_id not in self.stacks or self.stacks[thread_id] != stack:
                self.stacks[thread_id] = stack
                self.times[thread_id] = time()
            elif time() - self.times[thread_id] >= self.max_same_stack_time:
                self.printe("\n*** POSSIBLE DEADLOCK IN THREAD %d DETECTED: - ***\n" % thread_id)
                self.deadlock_found = True
                self.stacks.pop(thread_id)
                self.times.pop(thread_id)
                self.print_all_stacks()
