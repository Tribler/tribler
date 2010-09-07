# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements a generic console interface that can
be attached to any runnable python object.
"""

import code
import __builtin__
import threading
import exceptions

##############################################
# OBJECT CONSOLE
##############################################

class ConsoleError(exceptions.Exception):
    """Error associated with the console."""
    pass

class ObjectConsole:

    """
    This class runs a python console in the main thread, and starts 
    a given Object in a second thread.
    
    The Object is assumed to implement at least two methods, run() and stop().
    - The run() method is the entry point for the thread.
    - The stop() method is used by the main thread to request that the
    object thread does a controlled shutdown and returns from the run method.
    If the worker thread does not return from run() within 2 seconds after stop()
    has been invoked, the console terminates the object thread more aggressively.
    
    AttributeNames of Object listed in the provided namespace will be 
    included in the console namespace. 
    """
    TIMEOUT = 2


    def __init__(self, object_, name_space=None, run='run', 
                 stop='stop', name=""):

        self._object = object_
        self._object_run = getattr(object_, run)
        self._object_stop = getattr(object_, stop)        
        self._thread = threading.Thread(group=None, 
                                        target=self._object_run, 
                                        name="ObjectThread")

        # Configure Console Namespace
        self._name_space = {}
        self._name_space['__builtiname_space__'] = __builtin__
        self._name_space['__name__'] = __name__
        self._name_space['__doc__'] = __doc__
        self._name_space['help'] = self._usage

        if name_space and isinstance(name_space, type({})):
            self._name_space.update(name_space)

        self._app_name_space = name_space
        self._app_name = name
        self._usage()


    def _usage(self):
        """Print usage information."""
        print "\nConsole:", self._app_name
        for key in self._app_name_space.keys():
            print "- ", key
        print "-  help"

    def run(self):
        """Starts the given runnable object in a thread and 
        then starts the console."""
        self._thread.start()
        try:
            code.interact("", None, self._name_space)
        except KeyboardInterrupt:
            pass
        self._object_stop()
        self._thread.join(ObjectConsole.TIMEOUT)
        if self._thread.isAlive():
            raise ConsoleError, "Worker Thread still alive"

