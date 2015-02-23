# Written by Arno Bakker
# see LICENSE.txt for license information
""" Base classes for the Core API """

from Tribler.Core.exceptions import NotYetImplementedException

#
# Tribler API base classes
#


class Serializable(object):

    """
    Interface to signal that the object is pickleable.
    """

    def __init__(self):
        pass


class Copyable(object):

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


class ContentDefinition(object):

    """ Interface for content definition such as torrents and swift swarms """

    def get_name(self):
        """ Returns the user-friendly name of this Definition
        @return string
        """
        raise NotYetImplementedException()
