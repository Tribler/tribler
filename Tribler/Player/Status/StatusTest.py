# Written by Njaal Borch
# see LICENSE.txt for license information


import unittest
import threading

import time

import Status
import LivingLabReporter

class TestOnChangeStatusReporter(Status.OnChangeStatusReporter):
    
    name = None
    value = None

    def report(self, element):
        self.name = element.name
        self.value = element.value

class TestPeriodicStatusReporter(Status.PeriodicStatusReporter):
    last_value = None

    def report(self):
        # Actually report
        assert len(self.elements) == 1
        self.last_value = self.elements[0].get_value()

class StatusTest(unittest.TestCase):
    """
    Unit tests for the Status class

    
    """
    
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    def testBasic(self):

        status = Status.get_status_holder("UnitTest")
        
        self.assertNotEqual(status, None)

        self.assertEquals(status.get_name(), "UnitTest")
        
    def testInt(self):
        
        status = Status.get_status_holder("UnitTest")
        self.assertNotEqual(status, None)

        i = status.create_status_element("TestInteger", "A test value")
        self.assertEquals(i.get_name(), "TestInteger")

        x = status.get_status_element("TestInteger")
        self.assertEquals(x, i)

        # Test set and get values
        for j in range(0,10):
            i.set_value(j)
            self.assertEquals(i.get_value(), j)

        # Clean up
        status.remove_status_element(i)
        try:
            status.get_status_element("TestInteger")
            self.fail("Remove does not remove status element 'TestInteger'")
        except Status.NoSuchElementException, e:
            # Expected
            pass

    def testInvalid(self):
        status = Status.get_status_holder("UnitTest")

        try:
            i = status.create_status_element(None, "A number")
            self.fail("Does not throw exception with no name")
        except AssertionError, e:
            pass

        try:
            status.get_status_element(None)
            self.fail("Invalid get_status_element does not throw exception")
        except AssertionError,e:
            pass

        try:
            status.remove_status_element(None)
            self.fail("Invalid remove_status_element does not throw exception")
        except AssertionError,e:
            pass

        elem = Status.StatusElement("name", "description")
        try:
            status.remove_status_element(elem)
            self.fail("Invalid remove_status_element does not throw exception")
        except Status.NoSuchElementException,e:
            pass
            
        
    def testPolicy_ON_CHANGE(self):

        status = Status.get_status_holder("UnitTest")
        reporter = TestOnChangeStatusReporter("On change")
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger", "Some number")

        for x in range(0, 10):
            i.set_value(x)
            if x != reporter.value:
                self.fail("Callback does not work for ON_CHANGE policy")
            if reporter.name != "TestInteger":
                self.fail("On_Change callback get's the wrong parameter, got '%s', expected 'TestInteger'"%reporter.name)

        # Clean up
        status.remove_status_element(i)
        

    def testPolicy_PERIODIC(self):

        status = Status.get_status_holder("UnitTest")
        reporter = TestPeriodicStatusReporter("Periodic, 0.4sec", 0.4)
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger", "An integer")

        for x in range(0, 5):
            i.set_value(x)
            self.assertEquals(reporter.last_value, None) # Not updated yet
            
        time.sleep(1)
        
        assert reporter.last_value == 4

        for x in range(5, 9):
            self.assertEquals(reporter.last_value, 4) # Not updated yet
            i.set_value(x)
        time.sleep(1)

        self.assertEquals(reporter.last_value, 8)

        # Clean up
        status.remove_status_element(i)

        reporter.stop()

    def test_LLReporter(self):
        
        status = Status.get_status_holder("UnitTest")
        reporter = TestLivingLabPeriodicReporter("Living lab test reporter", 1.0)
        status.add_reporter(reporter)
        i = status.create_status_element("TestInteger", "An integer")
        i.set_value(1234)

        reporter.wait_for_post(5.0)

        reporter.stop()
        time.sleep(1)

class TestLivingLabPeriodicReporter(LivingLabReporter.LivingLabPeriodicReporter):

    def __init__(self, name, report_time):
        LivingLabReporter.LivingLabPeriodicReporter.__init__(self, name, report_time)
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
        #print xml
        self.xml = xml
        self.cond.acquire()
        self.cond.notifyAll()
        self.cond.release()
        
if __name__ == "__main__":

    print "Testing Status module"
    
    unittest.main()
    
    print "All done"
