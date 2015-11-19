# tribler_exe.py ---
#
# Filename: tribler_exe.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Mon Oct 19 17:10:59 2015 (+0200)

# Commentary:
#
# Tribler launcher to be used when freezing with py2exe.
#
# It levels the field across OSes in regards to imports, paths, etc.
#
# The only target of this module is to find tribler.py and execute it's __main__ method.
#
# It will also move the windows log file away so errors from different runs don't
# get mixed up.
#
# Shouldn't be executed directly nor used for anything else.

# change Log:
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

"""
Contains code to run Tribler from a .exe (used on Windows).
"""

import ctypes
import os
import sys


# From: https://measureofchaos.wordpress.com/2011/03/04/python-on-windows-unicode-environment-variables/
def get_environment_variable(name):
    """Get the unicode version of the value of an environment variable
    """
    env_variable = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)
    if env_variable == 0:
        return None
    buf = ctypes.create_unicode_buffer(u'\0' * env_variable)
    ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, env_variable)
    return buf.value

LOG_PATH = os.path.join(get_environment_variable(u"APPDATA"), u"Tribler.exe.log")
OLD_LOG_PATH = os.path.join(get_environment_variable(u"APPDATA"), u"Tribler.exe.old.log")

if os.path.exists(OLD_LOG_PATH):
    try:
        os.remove(OLD_LOG_PATH)
    except OSError:
        pass

if os.path.exists(LOG_PATH):
    try:
        os.rename(LOG_PATH, OLD_LOG_PATH)
    except OSError:
        print >> sys.stderr, "Unable to rename the log file!"

INSTALL_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))

if INSTALL_DIR not in sys.path:
    sys.path.append(INSTALL_DIR)

from Tribler.Main.tribler import __main__

__main__()

#
# tribler_exe.py ends here
