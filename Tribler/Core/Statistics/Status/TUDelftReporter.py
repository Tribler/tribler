from Tribler.Core.Utilities.encoding import encode
from bz2 import compress
from time import time
import sys

from LivingLabReporter import LivingLabPeriodicReporter

DEBUG = False

class TUDelftReporter(LivingLabPeriodicReporter):
    host = "dispersyreporter.tribler.org"
    path = "/post.py"

    def __init__(self, name, frequency, public_key):
        LivingLabPeriodicReporter.__init__(self, name, frequency, public_key)
        # note: public_key is set to self.device_id

    def report(self):
        if DEBUG: print >> sys.stderr, "TUDelftReporter: report"
        events = self.get_events()
        if events:
            events = [{"name":event.get_name(), "time":event.get_time(), "values":event.get_values()} for event in events]
            data = (time(), self.device_id.encode("HEX"), events)
            compressed = compress(encode(data))
            if DEBUG: print >> sys.stderr, "TUDelftReporter: posting", len(compressed), "bytes payload"
            self.post(compressed)
        else:
            if DEBUG: print >> sys.stderr, "TUDelftReporter: Nothing to report"

if __debug__:
    if __name__ == "__main__":
        from Tribler.Core.Statistics.Status.Status import get_status_holder

        status = get_status_holder("dispersy-simple-dispersy-test")
        status.add_reporter(TUDelftReporter("Periodically flush events to TUDelft", 5, "blabla"))
        status.create_and_add_event("foo", ["foo", "bar"])
        status.create_and_add_event("animals", ["bunnies", "kitties", "doggies"])
        status.create_and_add_event("numbers", range(255))

        from time import sleep
        sleep(15)
