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

import os
import sys
import ctypes

# WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!
#
# There's a copy of the following two functions in hacks.py due to this file
# depending on them to be able to update the PYTHONPATH so it can import anything
# else and this file being deleted when py2exe freezes it. So please, if you
# modify them, update their twin brothers too!
#
# WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!

# TODO(emilon): remove this when Tribler gets migrated to python 3.
# From: https://measureofchaos.wordpress.com/2011/03/04/python-on-windows-unicode-environment-variables/
def get_environment_variable(name):
    """Get the unicode version of the value of an environment variable
    """
    name = unicode(name)
    n = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)
    if n == 0:
        return None
    buf = ctypes.create_unicode_buffer(u'\0' * n)
    ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, n)
    return buf.value

def set_environment_variable(name, value):
    """Unicode compatible environment variable setter
    """
    if ctypes.windll.kernel32.SetEnvironmentVariableW(name, value) == 0:
        raise RuntimeError("Failed to set env. variable '%s' to '%s" %
                           (repr(name), repr(value)))

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
        pass

# TODO(emilon): This hijacks py2exe's hijacked stderr with a version that uses
# the right log location. This should go away the second we start using something
# else.
if sys.frozen == "windows_exe": # py2exe sets this. pylint: disable=no-member
    class Stderr(object):
        p2e_stderr = sys.stderr

        def write(self, text, alert=None, fname=LOG_PATH): # pylint: disable=unused-argument
            self.p2e_stderr.write(text, fname=fname)

        def flush(self):
            self.p2e_stderr.flush()

    sys.stderr = Stderr()
    del Stderr

    class Blackhole(object):
        softspace = 0
        def write(self, text):
            pass
        def flush(self):
            pass
    sys.stdout = Blackhole()
    del Blackhole
# END OF INCEPTION

INSTALL_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))

if INSTALL_DIR not in sys.path:
    sys.path.append(INSTALL_DIR)

set_environment_variable("PATH", os.path.abspath(INSTALL_DIR) + os.pathsep + get_environment_variable(u"PATH"))

from Tribler.Main.tribler import __main__  # pylint: disable=wrong-import-position

__main__()

#
# tribler_exe.py ends here
