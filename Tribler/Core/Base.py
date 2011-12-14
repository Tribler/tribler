# Written by Arno Bakker
# see LICENSE.txt for license information
""" Base classes for the Core API """

from Tribler.Core.exceptions import *

DEBUG = False

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


class ContentDefinition:
    """ Interface for content definition such as torrents and swift swarms """
    
    def get_def_type(self):
        """ Returns the type of this Definition
        @return string
        """
        raise NotYetImplementedException()

    def get_name(self):
        """ Returns the user-friendly name of this Definition
        @return string
        """
        raise NotYetImplementedException()
    