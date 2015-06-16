# Written by Arno Bakker
# see LICENSE.txt for license information
""" Base classes for the Core API """

from Tribler.Core.exceptions import NotYetImplementedException

#
# Tribler API base classes
#
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
