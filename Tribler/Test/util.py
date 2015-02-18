# util.py ---
#
# Filename: util.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Feb 18 18:03:06 2015 (+0100)

# Commentary:
#
# based on the code from http://code.activestate.com/recipes/52215/
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:


import logging
import sys

#logging.basicConfig()

__all__ = ["check_and_reset_exception_raised"]

class UnhandledExceptionCatcher(object):

    """
    Log the usual tb information, followed by a listing of all the
    local variables in each frame and mark the test run as failed.
    """

    def __init__(self):
        self.unhandled_exception_raised = False
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.debug("setting catch_exception() as sys.excepthook")
        sys.excepthook = self.catch_exception

    def catch_exception(self, type, value, tb):
        self.unhandled_exception_raised = True

        self.logger.critical("Unhandled exception raised while running the test: %s %s", type, value)

        stack = []
        while tb:
            stack.append(tb.tb_frame)
            tb = tb.tb_next

        self.logger.critical("Locals by frame, innermost last:")
        for frame in stack:
            self.logger.critical("%s in %s:%s", frame.f_code.co_name,
                                 frame.f_code.co_filename,
                                 frame.f_lineno)
            for key, value in frame.f_locals.items():
                try:
                    value = repr(value)
                except:
                    value = "<Error while REPRing value>"
                self.logger.critical("\t%10s = %s", key, value)

    def check_and_reset_exception_raised(self):
        raised = self.unhandled_exception_raised
        self.unhandled_exception_raised = False
        return raised

_catcher = UnhandledExceptionCatcher()

check_and_reset_exception_raised = _catcher.check_and_reset_exception_raised


#
# util.py ends here
