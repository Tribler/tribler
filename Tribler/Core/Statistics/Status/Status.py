# Written by Njaal Borch
# see LICENSE.txt for license information

import threading
import time

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
    """
    Parent exception for all status based exceptions
    """
    pass

class NoSuchElementException(StatusException):
    """
    No such element found
    """
    pass

class NoSuchReporterException(StatusException):
    """
    Unknown reporter
    """
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
        self.events = []

    def reset(self):
        """
        Reset everything to blanks!
        """
        self.elements = {}
        self.reporters = {}
        self.events = []

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
            return self.reporters[name]
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
                raise Exception("Already have reporter '%s' registered"% \
                                reporter.name)
            self.reporters[reporter.name] = reporter

            # The reporter must contact me later
            reporter.add_status_holder(self)
            
            # If we have any other reporters, copy the elements
            # to the new one
            for element in self.elements.values():
                reporter.add_element(element)
        finally:
            self.lock.release()
            

    def _add_element(self, new_element):
        for reporter in self.reporters.values():
            reporter.add_element(new_element)
        

    def create_status_element(self, name, initial_value=None):
        assert name
        
        new_element = StatusElement(name, initial_value)

        self.lock.acquire()
        try:
            if name in self.elements:
                raise Exception("Already have a status element with the given name")
            self.elements[name] = new_element
            self._add_element(new_element)
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
        
    def get_or_create_status_element(self, name, initial_value=None):
        self.lock.acquire()
        if not name in self.elements:
            self.lock.release()
            return self.create_status_element(name, initial_value)
        try:
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
            
    def create_event(self, name, values=[]):
        return EventElement(name, values)

    def add_event(self, event):
        self.lock.acquire()
        try:
            self.events.append(event)
            self._add_element(event)
        finally:
            self.lock.release()

    def remove_range(self, range):
        self.remove_event(range)
        
    def remove_event(self, event):
        self.lock.acquire()
        try:
            if event in self.events:
                self.events.remove(event)
        finally:
            self.lock.release()
        
    def create_and_add_event(self, name, values=[]):
        self.add_event(self.create_event(name, values))

    def create_range(self, name, values=[]):
        return RangeElement(name, values)

    def add_range(self, range):
        self.add_event(range)
        
    def create_and_add_range(self, name, values=[]):
        self.add_range(self.create_range(name, values))

    def get_elements(self):
        """
        Reporters will use this to get a copy of all
        elements that should be reported
        """
        self.lock.acquire()
        try:
            return self.elements.values()[:]
        finally:
            self.lock.release()

    def get_events(self):
        """
        Reporters will use this to get a copy of all
        events that should be reported
        """
        self.lock.acquire()
        try:
            events = self.events
            self.events = []
            return events
        finally:
            self.lock.release()

    def report_now(self):
        """
        Forces all reporters to report now
        """
        for reporter in self.reporters.values():
            reporter.report_now()

        
        
class BaseElement:
    type = "BaseElement"

    def __init__(self, name):
        """
        Create a new element.  DO NOT USE THIS - use
        create_status_element() using a Status Holder object
        """
        assert name
        self.name = name
        self.callbacks = []
        self.lock = threading.Lock()

    def get_type(self):
        return self.type

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

    def get_name(self):
        return self.name

                           
    def _updated(self):
        """
        When a status element is changed, this method must be called to
        notify any reporters
        """

        # TODO: Lock or make a copy?
        
        for callback in self.callbacks:
            try:
                callback(self)
            except Exception, e:
                import sys
                print >> sys.stderr, "Exception in callback", \
                      callback,"for parameter",self.name,":",e

        
class StatusElement(BaseElement):
    """
    Class to hold status information
    """
    type = "status report"

    def __init__(self, name, initial_value=None):
        """
        Create a new element.  DO NOT USE THIS - use
        create_status_element() using a Status Holder object
        """
        BaseElement.__init__(self, name)
        self.value = initial_value

    def set_value(self, value):
        """
        Update the value of this status element
        """
        
        self.value = value
        self._updated()
        
    def get_value(self):
        return self.value

    def inc(self, value=1):
        """
        Will only work for numbers!
        """
        self.lock.acquire()
        try:
            self.value += value
            self._updated()
        except:
            raise Exception("Can only increment numbers")
        finally:
            self.lock.release()

    def dec(self, value=1):
        """
        Will only work for numbers!
        """
        self.lock.acquire()
        try:
            self.value -= value
            self._updated()
        except:
            raise Exception("Can only increment numbers")
        finally:
            self.lock.release()

        
class EventElement(BaseElement):
    type = "event"

    def __init__(self, name, values=[]):
        """
        Create a new element.  DO NOT USE THIS - use
        create_status_element() using a Status Holder object
        """
        self.time = long(time.time())
        BaseElement.__init__(self, name)
        self.values = values

    def get_time(self):
        return self.time

    def add_value(self, value):
        self.lock.acquire()
        try:
            self.values.append(value)
        finally:
            self.lock.release()

    def get_values(self):
        """
        Return the values as a copy to ensure that there are no
        synchronization issues
        """
        self.lock.acquire()
        try:
            return self.values[:]
        finally:
            self.lock.release()

class RangeElement(BaseElement):
    type = "range"

    def __init__(self, name, values=[]):
        self.start_time = self.end_time = long(time.time())
        BaseElement.__init__(self, name, "range")
        self.values = values

    def get_start_time(self):
        return self.start_time

    def get_end_time(self):
        return self.end_time
        
    def add_value(self, value):
        self.lock()
        try:
            self.end_time = long(time.time())
            self.values.append(value)
        finally:
            self.lock.release()
            
    def get_values(self):
        """
        Return the values as a copy to ensure that there are no
        synchronization issues
        """
        self.lock()
        try:
            return self.values[:]
        finally:
            self.lock.release()
        
class StatusReporter:
    """
    This is the basic status reporter class.  It cannot be used
    directly, but provides a base for all status reporters.
    The status reporter is threadsafe
    """
    
    def __init__(self, name):
        self.name = name
        self.lock = threading.Lock()
        self.status_holders = []
        
    def add_status_holder(self, holder):
        if not holder in self.status_holders:
            self.status_holders.append(holder)
        
    def get_elements(self):
        """
        Return all elements that should be reported
        """
        elements = []
        for holder in self.status_holders:
            elements += holder.get_elements()
        return elements

    def get_events(self):
        """
        Return all elements that should be reported
        """
        events = []
        for holder in self.status_holders:
            events += holder.get_events()
        return events

    def report_now(self):
        """
        Forces the reporter to report now
        """
        pass


class OnChangeStatusReporter(StatusReporter):
    """
    A basic status reporter which calls 'report(element)' whenever
    it is changed
    """
    elements = []
    
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
        pass # To be implemented by the actual reporter

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
        
        StatusReporter.__init__(self, name)
        self.frequency = frequency
        self.parameters = []
        self.error_handler = error_handler

        # Set up the timer
        self.running = True
        self.create_timer()
        
    def create_timer(self):
        self.timer = threading.Timer(self.frequency, self.on_time_event)
        self.timer.setName("PeriodicStatusReporter_"+self.name)
        self.timer.setDaemon(True)
        self.timer.start()

    def stop(self, block=False):
        """
        Stop this reporter.  If block=True this function will not return
        until the reporter has actually stopped
        """
        self.timer.cancel()
        
        self.on_time_event()

        self.running = False
        self.timer.cancel()
        self.timer.join()
        
    def report(self):
        """
        This function must be overloaded, does nothing
        """
        raise Exception("Not implemented")

    def add_element(self, element):
        """
        Overload if you want your periodic reporter to only
        report certain elements of a holder. Normally this does
        nothing, but report fetches all elements
        """
        pass

    def on_time_event(self):
        """
        Callback function for timers
        """
        if self.running:
            self.create_timer()
            try:
                self.report()
            except Exception, e:
                if self.error_handler:
                    try:
                        self.error_handler(0, str(e))
                    except:
                        pass
                else:
                    print "Error but no error handler:", e
                    #import traceback
                    #traceback.print_stack()

    def report_now(self):
        """
        Forces the reporter to report now
        """
        try:
            self.report()
        except Exception, e:
            if self.error_handler:
                try:
                    self.error_handler(0, str(e))
                except:
                    pass
            else:
                print "Error but no error handler:", e
                #import traceback
                #traceback.print_stack()
        
        
if __name__ == "__main__":
    # Some basic testing (full unit tests are in StatusTest.py)
    
    print "Run unit tests"
    raise SystemExit(-1)
