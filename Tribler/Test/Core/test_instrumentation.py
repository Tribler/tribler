from threading import Event
from time import sleep
from Tribler.Core.Utilities.instrumentation import synchronized, WatchDog
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestInstrumentation(TriblerCoreTest):

    @synchronized
    def synchronized_func(self):
        return 42

    def test_synchronized_decorator(self):
        result = self.synchronized_func()
        self.assertEqual(result, 42)

    def test_watchdog(self):

        self.test_event = Event()
        self.test_event.set()

        self.watchdog = WatchDog()
        self.watchdog.debug = True
        self.watchdog.check_for_deadlocks = True
        self.watchdog.register_event(self.test_event, "42-event", 0.5)
        self.watchdog.start()
        sleep(1)

        self.watchdog.print_all_stacks()
        self.watchdog.unregister_event("42-event")
        self.watchdog.join()
