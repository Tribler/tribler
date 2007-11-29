# Written by Arno Bakker
# see LICENSE.txt for license information

import sys

from Tribler.Core.exceptions import *

DEBUG = True

#
# Tribler API base classes
#
class Serializable:
    """
    Interface to signal that the object is pickleable.
    """
    def __init__(self):
        pass

class Copyable:
    """
    Interface for copying an instance (or rather signaling that it can be 
    copied) 
    """
    def copy(self):
        """
        Copies the instance.
        @param self     an unbound instance of the class
        @return Returns a copy of "self"
        """
        raise NotYetImplementedException()
