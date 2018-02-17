from threading import Event, Thread

from Tribler.Core.Utilities.instrumentation import synchronized, WatchDog
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestSynchronized(TriblerCoreTest):
    def __init__(self, *argv, **kwargs):
        super(TriblerCoreTestSynchronized, self).__init__(*argv, **kwargs)

        self.counter = None

    def setUp(self):
        self.counter = 0

    def tearDown(self):
        self.counter = None

    @synchronized
    def _synchronized_func(self):
        return 42

    @synchronized
    def _up(self):
        self.counter += 1

    def test_synchronized_decorator_returns(self):

        result = self._synchronized_func()

        # Calling a decorated function still returns the correct value
        self.assertEqual(result, 42)

    def test_synchronized_decorator_synchronizes(self):
        THREADS_NUM = 5
        ADDER_ITERATIONS = 100

        # Event used to make sure all threads start adding at the same time
        start_event = Event()

        def add_a_bunch():
            start_event.wait(1)
            for _ in xrange(ADDER_ITERATIONS):
                self._up()

        # Create a bunch of threads that will call adder() at the same time
        threads = []
        for _ in xrange(THREADS_NUM):
            t = Thread(target=add_a_bunch)
            t.start()
            threads.append(t)

        start_event.set()

        # Wait for all threads to be done
        for t in threads:
            t.join()

        # counter is threads times iterations
        self.assertEqual(self.counter, THREADS_NUM * ADDER_ITERATIONS)


class TriblerCoreTestWatchDog(TriblerCoreTest):
    def setUp(self):
        self._test_event = Event()
        self._test_event.set()
        self._printe_event = Event()
        self.watchdog = WatchDog()

    def tearDown(self):
        if self.watchdog.is_alive():
            self.watchdog.join()

        self._test_event = None
        self._printe_event = None
        self.watchdog = None

    def _dummy_printe(self, _):
        self._printe_event.set()

    def test_watchdog_event(self):
        self.watchdog.printe = self._dummy_printe
        self.watchdog.register_event(self._test_event, "42-event", 0.2)

        # The event hasn't been set prematurelly
        self.assertFalse(self._printe_event.is_set())
        self.watchdog.start()

        # Something has been printed
        self.assertTrue(self._printe_event.wait(1))

        # The failed watchdog has been removed from the watch list
        with self.watchdog._synchronized_lock:
            self.assertNotIn("42-event", self.watchdog._registered_events.keys())

    def test_watchdog_event_debug(self):
        self.watchdog.printe = self._dummy_printe
        self.watchdog.debug = True
        self.watchdog.register_event(self._test_event, "42-event", 0.2)

        self.watchdog.start()

        # Something has been printed (the "watchdog is OK" message)
        self.assertTrue(self._printe_event.wait(1))

    def test_watchdog_print_all_stacks(self):
        self.watchdog.printe = self._dummy_printe

        # print_all_stacks() works on its own too
        self.assertFalse(self._printe_event.is_set())
        self.watchdog.print_all_stacks()
        self.assertTrue(self._printe_event.is_set())

    def test_watchdog_deadlock(self):
        self.watchdog.printe = self._dummy_printe
        self.watchdog.max_same_stack_time = 0
        self.watchdog.check_for_deadlocks = True

        # The event hasn't triggered before starting the watchdog
        self.assertFalse(self._printe_event.is_set())
        self.watchdog.start()
        # The even gets set when a thread has the same stack for more than 0 seconds.
        self.assertTrue(self._printe_event.wait(1))

    def test_watchdog_thread_name(self):
        """
        Test thread names outputted by watchdog
        """
        self.assertEquals("Unknown", self.watchdog.get_thread_name(-1))
