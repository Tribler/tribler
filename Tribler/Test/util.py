# util.py ---
#
# Filename: util.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Feb 18 18:03:06 2015 (+0100)

# Commentary:
#
# partially based on the code from http://code.activestate.com/recipes/52215/
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

# logging.basicConfig()

__all__ = ["process_unhandled_exceptions"]


class UnhandledExceptionCatcher(object):

    """
    Logs the usual tb information, followed by a listing of all the
    local variables in each frame and mark the test run as failed.
    """

    def __init__(self):
        self._lines = []
        self._logger = logging.getLogger(self.__class__.__name__)
        sys.excepthook = self.catch_exception

    def _register_exception_line(self, line, *format_args):
        line = line % format_args
        self._lines.append(line)
        self._logger.critical(line)

    def catch_exception(self, type, value, tb):
        def repr_(value):
            try:
                return repr(value)
            except:
                return "<Error while REPRing value>"

        self._register_exception_line("Unhandled exception raised while running the test: %s %s", type, repr_(value))

        stack = []
        while tb:
            stack.append(tb.tb_frame)
            tb = tb.tb_next

        self._register_exception_line("Locals by frame, innermost last:")
        for frame in stack:
            self._register_exception_line("%s:%s %s:", frame.f_code.co_filename,
                                          frame.f_lineno, frame.f_code.co_name)
            for key, value in frame.f_locals.items():
                value = repr_(value)
                self._register_exception_line("| %12s = %s", key, value)

    def check_exceptions(self, unittest):
        if self._lines:
            lines = self._lines
            self._lines = []

            self._logger.critical("The following unhandled exceptions where raised during this test's execution:")
            for line in lines:
                self._logger.critical(line)

            raise Exception("Test got unhandled exceptions")

_catcher = UnhandledExceptionCatcher()

process_unhandled_exceptions = _catcher.check_exceptions


#
# util.py ends here
