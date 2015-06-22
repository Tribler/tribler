# twisted.py ---
#
# Filename: twisted.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Mon Jun 22 13:13:36 2015 (+0200)

# Commentary:
#
# Misc. utility methods and classes for twisted.
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

from threading import current_thread

from twisted.internet import reactor


def callInThreadPool(fun, *args, **kwargs):
    """
    Calls fun(*args, **kwargs) in the reactor's thread pool.
    """
    if isInThreadPool():
        fun(*args, **kwargs)
    else:
        reactor.callFromThread(reactor.callInThread, fun, *args, **kwargs)


def isInThreadPool():
    """
    Check if we are currently on one of twisted threadpool threads.
    """
    return current_thread() in reactor.threadpool.threads


#
# twisted.py ends here
