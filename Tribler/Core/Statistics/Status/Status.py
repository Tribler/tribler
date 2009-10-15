# Written by Njaal Borch
# see LICENSE.txt for license information


import sys
import threading
import time
import traceback

# Factory vars
global status_holders
status_holders = {}
global status_lock
status_lock = threading.Lock()

def get_status_holder(name):
    global status_lock
    global status_holders
    status_lock.acquire()
    try:
        if not name in status_holders:
            status_holders[name] = StatusHolder(name)

        return status_holders[name]
    finally:
        status_lock.release()

class StatusException(Exception):
    pass

class NoSuchElementException(StatusException):
    pass

class NoSuchReporterException(StatusException):
    pass

# Policies
#ON_CHANGE = 1
#PERIODIC = 2

class StatusHolder:

    """
    A class to hold (and report) status information for an application.
    A status holder can have multiple reporters, that will report status
    information on change or periodically.

    """


    def __init__(self, name):
        """
        Do not create new status objects if you don't know what you're doing.
        Use the getStatusHolder() function to retrieve status objects.
        """
        self.name = name
        self.elements = {}
        self.reporters = {}
        self.lock = threading.Lock()
        
    def get_name(self):
        """
        Return the name of this status holder
        """
        return self.name

    def get_reporter(self, name):
        """
        Get a given reporter from the status holder, using the name of the
        reporter.
        """
        assert name
        
        self.lock.acquire()
        try:
            if not name in self.reporters:
                raise Exception("No such reporter '%s'"%name)
            return self.reporter[name]
        finally:
            self.lock.release()
            
    def add_reporter(self, reporter):
        """
        Add a reporter to this status object.
        """
        assert reporter
        
        self.lock.acquire()
        try:
            if reporter.name in self.reporters:
                raise Exception("Already have reporter '%s' registered"%reporter.name)
            self.reporters[reporter.name] = reporter
            
            # If we have any other reporters, copy the elements
            # to the new one
            for element in self.elements.values():
                reporter.add_element(element)
        finally:
            self.lock.release()
        
    def create_status_element(self, name, description, initial_value=None):
        assert name
        assert description
        
        new_element = StatusElement(name, description, initial_value)

        self.lock.acquire()
        try:
            if name in self.elements:
                raise Exception("Already have a status element with the given name")
            self.elements[name] = new_element # "local" copy
            for reporter in self.reporters.values():
                reporter.add_element(new_element)
        finally:
            self.lock.release()

        return new_element
            
    def get_status_element(self, name):
        """
        Get a status element from the Status Holder by name
        """
        assert name
        
        self.lock.acquire()
        try:
            if not name in self.elements:
                raise NoSuchElementException(name)
            return self.elements[name]
        finally:
            self.lock.release()
        
    def remove_status_element(self, element):
        """
        Remove a status element
        """
        assert element
        
        self.lock.acquire()
        try:
            if not element.name in self.elements:
                raise NoSuchElementException(element.name)
            del self.elements[element.name]

            # Also remove this element to the policy
            for reporter in self.reporters.values():
                # TODO: More elegant here
                try:
                    reporter.remove_element(element)
                except:
                    pass

        finally:
            self.lock.release()

class StatusElement:
    """
    Class to hold status information
    """
    def __init__(self, name, description, initial_value=None):
        """
        Create a new element.  DO NOT USE THIS - use
        create_status_element() using a Status Holder object
        """
        assert name
        self.name = name
        self.descripton = description
        self.value = initial_value
        self.callbacks = []
        
        # TODO: Do I need locks here?
    def get_name(self):
        return self.name

    def set_value(self, value):
        """
        Update the value of this status element
        """
        self.value = value
        result = True
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception, e:
                # 04/06/09: I would prefer to raise the exception
                # here... at the very least I have added a True/False
                # return value
                result = False
                traceback.print_exc()
                print >>sys.stderr, "Exception in callback",callback,"for parameter",self.name
                print >>sys.stderr, e
        return result
        
    def get_value(self):
        return self.value

    def add_callback(self, callback):
        """
        Add a callback that will be executed when this element is changed.
        The callback function will be passed the status element itself
        """
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        """
        Remove an already registered callback
        """
        if not callback in self.callbacks:
            raise Exception("Cannot remove unknown callback")

class StatusReporter:
    """
    This is the basic status reporter class.  It cannot be used
    directly, but provides a base for all status reporters.
    The status reporter is threadsafe
    """
    
    def __init__(self, name, error_handler=None):
        self.name = name
        self.lock = threading.Lock()
        self.elements = []
        self.error_handler = error_handler

    def get_name(self):
        return self.name

    def add_element(self, element):
        """
        Add a status element to this reporter
        """
        self.lock.acquire()
        try:
            if element in self.elements:
                raise Exception("Element %s already registered"%element.name)
            self.elements.append(element)
        finally:
            self.lock.release()

    def remove_element(self, element):
        """
        Remove a status element from this reporter
        """
        
        self.lock.acquire()
        try:
            if not element in self.elements:
                raise NoSuchElementException("Element %s unknown"%element.name)
            self.elements.remove(element)
        finally:
            self.lock.release()

class OnChangeStatusReporter(StatusReporter):
    """
    A basic status reporter which calls 'report(element)' whenever
    it is changed
    """

    def add_element(self, element):
        """
        Add element to this reporter
        """
        element.add_callback(self.report)
        
    def remove_element(self, element):
        """
        Remove an element from this reporter
        """
        element.remove_callback(self.report)
        
    def report(self, element):
        """
        This function must be implemented by and extending class. Does nothing.
        """
        raise NotImplemented("To be implemented by the actual reporter")

class PeriodicStatusReporter(StatusReporter):
    """
    Base class for a periodic status reporter, calling report(self)
    at given times.  To ensure a nice shutdown, execute stop() when
    stopping.
    
    """
    
    def __init__(self, name, frequency, error_handler=None):
        """
        Frequency is a float in seconds
        Error-handler will get an error code and a string as parameters,
        the meaning will be up to the implemenation of the
        PeriodicStatusReporter.
        """
        
        StatusReporter.__init__(self, name, error_handler=error_handler)
        self.frequency = frequency
        self.parameters = []

        # Set up the timer
        self.running = True
        self.timer = threading.Timer(self.frequency, self.on_time_event)
        self.timer.start()

    def stop(self, block=False):
        """
        Stop this reporter.  If block=True this function will not return
        until the reporter has actually stopped
        """
        self.running = False
        self.timer.cancel()
        self.timer.join()
        
    def report(self):
        """
        This function must be overloaded, does nothing
        """
        raise NotImplemented("To be implemented by the actual reporter")

    def on_time_event(self):
        """
        Callback function for timers
        """
        if self.running:
            self.timer = threading.Timer(self.frequency, self.on_time_event)
            self.timer.start()
            self.report()

            # try:
            # except Exception,e:
            #     if self.error_handler:
            #         traceback.print_exc()
            #         try:
            #             self.error_handler(0, str(e))
            #         except:
            #             pass
        
if __name__ == "__main__":
    # Some basic testing (full unit tests are in StatusTest.py)
    
    print "Run unit tests"
    raise SystemExit(-1)
