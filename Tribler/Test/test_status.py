# Written by Njaal Borch
# see LICENSE.txt for license information
import unittest
import threading

import time

from Tribler.Core.Statistics.Status import Status
from Tribler.Core.Statistics.Status import LivingLabReporter
from Tribler.Test.test_as_server import AbstractServer


raise unittest.SkipTest("We are not using any of this")

class TestOnChangeStatusReporter(Status.OnChangeStatusReporter):

    name = None
    value = None

    def report(self, element):
        self.name = element.name
        self.value = element.value


class TestPeriodicStatusReporter(Status.PeriodicStatusReporter):
    last_value = None

    def report(self):
        elements = self.get_elements()
        # Actually report
        assert len(elements) == 1
        self.last_value = elements[0].get_value()


class StatusTest(AbstractServer):

    """
    Unit tests for the Status class

    """

    def testBasic(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()

        self.assertNotEqual(status, None)

        self.assertEquals(status.get_name(), "UnitTest")

    def testInt(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()
        self.assertNotEqual(status, None)

        i = status.create_status_element("TestInteger")
        self.assertEquals(i.get_name(), "TestInteger")

        x = status.get_status_element("TestInteger")
        self.assertEquals(x, i)

        # Test set and get values
        for j in range(0, 10):
            i.set_value(j)
            self.assertEquals(i.get_value(), j)

        # Clean up
        status.remove_status_element(i)
        try:
            status.get_status_element("TestInteger")
            self.fail("Remove does not remove status element 'TestInteger'")
        except Status.NoSuchElementException as e:
            # Expected
            pass

    def testInvalid(self):
        status = Status.get_status_holder("UnitTest")
        status.reset()

        try:
            i = status.create_status_element(None)
            self.fail("Does not throw exception with no name")
        except AssertionError as e:
            pass

        try:
            status.get_status_element(None)
            self.fail("Invalid get_status_element does not throw exception")
        except AssertionError as e:
            pass

        try:
            status.remove_status_element(None)
            self.fail("Invalid remove_status_element does not throw exception")
        except AssertionError as e:
            pass

        elem = Status.StatusElement("name", "description")
        try:
            status.remove_status_element(elem)
            self.fail("Invalid remove_status_element does not throw exception")
        except Status.NoSuchElementException as e:
            pass

    def testPolicy_ON_CHANGE(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()
        reporter = TestOnChangeStatusReporter("On change")
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger")

        for x in range(0, 10):
            i.set_value(x)
            if x != reporter.value:
                self.fail("Callback does not work for ON_CHANGE policy")
            if reporter.name != "TestInteger":
                self.fail("On_Change callback get's the wrong parameter, got '%s', expected 'TestInteger'" % reporter.name)

        # Clean up
        status.remove_status_element(i)

    def testPolicy_PERIODIC(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()

        reporter = TestPeriodicStatusReporter("Periodic, 0.4sec", 0.4)
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger")

        for x in range(0, 5):
            i.set_value(x)
            self.assertEquals(reporter.last_value, None)  # Not updated yet

        time.sleep(1)

        assert reporter.last_value == 4

        for x in range(5, 9):
            self.assertEquals(reporter.last_value, 4)  # Not updated yet
            i.set_value(x)
        time.sleep(1)

        self.assertEquals(reporter.last_value, 8)

        # Clean up
        status.remove_status_element(i)

        reporter.stop()

    def test_LLReporter_element(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()
        reporter = TestLivingLabPeriodicReporter("Living lab test reporter", 1.0)
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger")
        i.set_value(1233)

        b = status.create_status_element("Binary")
        b.set_value("".join([chr(n) for n in range(0, 255)]))

        reporter.wait_for_post(5.0)

        reporter.stop()
        time.sleep(1)

        self.assertEquals(len(reporter.get_errors()), 0)

        status.remove_status_element(i)
        status.remove_status_element(b)

    def test_LLReporter_event(self):

        status = Status.get_status_holder("UnitTest")
        status.reset()
        reporter = TestLivingLabPeriodicReporter("Living lab test reporter", 1.0)
        status.add_reporter(reporter)
        event = status.create_event("SomeEvent")
        event.add_value("123")
        event.add_value("456")
        status.add_event(event)

        reporter.wait_for_post(5.0)

        reporter.stop()
        time.sleep(1)

        self.assertEquals(len(reporter.get_errors()), 0)

        status.remove_event(event)


class TestLivingLabPeriodicReporter(LivingLabReporter.LivingLabPeriodicReporter):

    def __init__(self, name, report_time):
        self.errors = []
        LivingLabReporter.LivingLabPeriodicReporter.__init__(self, name, report_time, "myid", self.count_errors)
        self.xml = None
        self.cond = threading.Condition()

    def wait_for_post(self, timeout):
        self.cond.acquire()
        try:
            if self.xml:
                return True

            self.cond.wait(timeout)
            if self.xml:
                return True
            raise Exception("Timeout")
        finally:
            self.cond.release()

    def post(self, xml):
        # TODO: Check the XML?
        print xml
        self.xml = xml
        self.cond.acquire()
        self.cond.notifyAll()
        self.cond.release()

    def count_errors(self, zero, error):
        print "ERROR", error
        self.errors.append(error)

    def get_errors(self):
        return self.errors

if __name__ == "__main__":

    print "Testing Status module"

    unittest.main()

    print "All done"
