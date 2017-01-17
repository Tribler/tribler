# hacks.py ---
#
# Filename: hacks.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Oct 14 16:19:42 2015 (+0200)

# Commentary:
#
# This file should contain code for hacks needed to work around bugs in non-tribler code.
#
# If you find, any existing code that matches this description, please, move it here and
# call it from the original spot.

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

# Needed because of python-cryptography doing weird stuff when scanning for backends.
# Should be removed as soon as https://github.com/pyca/cryptography/issues/2039 gets closed.
# This code is based on https://github.com/pyca/cryptography/issues/2039#issuecomment-115432291
# with some modifications so it only gets called when running an installer version of Tribler on windows.

import sys

# Python2 sys.argv uses the non-unicode windows API, so non-ascii chars will be mangled.
# TODO(emilon): This should be removed once we move to Python3
# Based on code from:
# https://stackoverflow.com/questions/846850/read-unicode-characters-from-command-line-arguments-in-python-2-x-on-windows
def get_unicode_sys_argv():
    """Uses shell32.GetCommandLineArgvW to get sys.argv as a list of Unicode
    strings.

    Versions 2.x of Python don't support Unicode in sys.argv on
    Windows, with the underlying Windows API instead replacing multi-byte
    characters with '?'.
    """

    from ctypes import POINTER, byref, cdll, c_int, windll
    from ctypes.wintypes import LPCWSTR, LPWSTR

    GetCommandLineW = cdll.kernel32.GetCommandLineW
    GetCommandLineW.argtypes = []
    GetCommandLineW.restype = LPCWSTR

    CommandLineToArgvW = windll.shell32.CommandLineToArgvW
    CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
    CommandLineToArgvW.restype = POINTER(LPWSTR)

    cmd = GetCommandLineW()
    argc = c_int(0)
    argv = CommandLineToArgvW(cmd, byref(argc))
    if argc.value > 0:
        # Remove Python executable and commands if present
        start = argc.value - len(sys.argv)
        return [argv[i] for i in xrange(start, argc.value)]

# TODO(emilon): remove this when Tribler gets migrated to python 3.
if sys.platform == "win32":
    import ctypes

    # WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!
    #
    # There's a copy of the following two functions in tribler_exe.py due to this file
    # depending on them to be able to update the PYTHONPATH so it can import anything
    # else and this file being deleted when py2exe freezes it. So please, if you
    # modify them, update their twin brothers too!
    #
    # WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!

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

#
# hacks.py ends here
