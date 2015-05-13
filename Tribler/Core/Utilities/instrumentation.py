# instrumentation.py ---
#
# Filename: instrumentation.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Fri Jun 26 17:18:02 2015 (+0200)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:


import traceback
from os import sys
from threading import Thread
from time import sleep, time


class WatchDog(Thread):

    """
    Watchdog thread, will periodically check if all registered events are set and
    clear them.  If any if them is still cleared on the next iteration, a big fat
    warning will be printed along with some debug info to help debugging the
    issue.
    """

    def __init__(self):
        """

        """
        super(WatchDog, self).__init__()
        self.setDaemon(True)
        self.setName(self.__class__.__name__)
        self._registered_events = {}
        self.check_for_deadlocks = False

        self.should_stop = False
        self.deadlock_found = False
        self.stacks = {}
        self.event_timestamps = {}
        self.event_timeouts = {}
        self.tripped_canaries = []
        self.times = {}

    def _reset_state(self):
        self.should_stop = False
        self.deadlock_found = False
        self.stacks = {}
        self.event_timestamps = {}
        self.tripped_canaries = []
        self.times = {}

    def join(self, *argv, **kwargs):
        print >> sys.stderr, "Stopping watchdog"
        self.should_stop = True
        super(WatchDog, self).join(*argv, **kwargs)
        print >> sys.stderr, "Watchdog stopped"

    def register_event(self, event, name, timeout=10):
        self.event_timeouts[name] = timeout
        self.event_timestamps[name] = time()
        self._registered_events[name] = event

    def unregister_event(self, name):
        self.event_timeouts.pop(name)
        self.event_timestamps.pop(name)
        self._registered_events.pop(name)

    def run(self):
        self._reset_state()
        events_to_unregister = []
        while not self.should_stop:
            sleep(0.2)
            if self.check_for_deadlocks:
                self.look_for_deadlocks()
            for name, event in self._registered_events.iteritems():
                if event.is_set():
                    event.clear()
                    self.event_timestamps[name] = time()
                    print >> sys.stderr, "watchog", name, "is OK"
                elif (self.event_timestamps[name] + self.event_timeouts[name]) < time():
                    print >> sys.stderr, "watchog", name, "*******TRIPPED!******"
                    print >> sys.stderr, "disabling it and printing traces"
                    events_to_unregister.append(name)
                    self.print_all_stacks()
            while events_to_unregister:
                name = events_to_unregister.pop()
                print >> sys.stderr, ">>>>>>>>>", name
                self.tripped_canaries.append(name)
                self.unregister_event(name)
        print >> sys.stderr, ">>>>>>>>> I SHOULD STOP"


    def print_all_stacks(self):
        print >> sys.stderr, "\n*** STACKTRACE - START ***\n"
        code = []
        for threadId, stack in sys._current_frames().items():
            code.append("\n# ThreadID: %s" % threadId)
            for filename, lineno, name, line in traceback.extract_stack(stack):
                code.append('File: "%s", line %d, in %s' % (filename,
                                                            lineno, name))
                if line:
                    code.append("  %s" % (line.strip()))

        for line in code:
            print >> sys.stderr, line
        print >> sys.stderr, "\n*** STACKTRACE - END ***\n"

    def look_for_deadlocks(self):
        for threadId, stack in sys._current_frames().items():
            if threadId not in self.stacks or self.stacks[threadId] != stack:
                self.stacks[threadId] = stack
                self.times[threadId] = time.time()
            elif time.time() - self.times[threadId] >= 60:
                print >> sys.stderr, "\n*** POSSIBLE DEADLOCK IN THREAD %d DETECTED: - ***\n" % threadId
                self.deadlock_found = True
                self.stacks.pop(threadId)
                self.times.pop(threadId)
                self.print_all_stacks()

#
# instrumentation.py ends here
