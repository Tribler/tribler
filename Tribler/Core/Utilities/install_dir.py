# install_dir.py ---
#
# Filename: install_dir.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Mon Oct 19 16:15:11 2015 (+0200)

# Commentary:
#
#
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
import os.path
import sys

from Tribler.Core.osutils import is_android, get_home_dir


# This function is used from tribler.py too, but can't be there as tribler.py
# gets frozen into an exe on windows.
def determine_install_dir():
    # Niels, 2011-03-03: Working dir sometimes set to a browsers working dir
    # only seen on windows

    # apply trick to obtain the executable location
    # see http://www.py2exe.org/index.cgi/WhereAmI
    # Niels, 2012-01-31: py2exe should only apply to windows

    # TODO(emilon): tribler_main.py is not frozen, so I think the special
    # treatment for windows could be removed (Needs to be tested)
    if sys.platform == 'win32':
        def we_are_frozen():
            """Returns whether we are frozen via py2exe.
            This will affect how we find out where we are located."""
            return hasattr(sys, "frozen")

        def module_path():
            """ This will get us the program's directory,
            even if we are frozen using py2exe"""
            if we_are_frozen():
                return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding()))

            filedir = os.path.dirname(unicode(__file__, sys.getfilesystemencoding()))
            return os.path.abspath(os.path.join(filedir, '..', '..', '..'))

        return module_path()

    elif sys.platform == 'darwin':
        # On a packaged app, this file will be at:
        # Tribler.app/Contents/Resources/lib/Python2.7/site-packages.zip/Tribler/Core/Utilities/install_dir.py
        cur_file = os.path.dirname(__file__)
        if "site-packages.zip" in cur_file:
            return os.path.abspath(os.path.join(cur_file, '..', '..', '..', '..', '..', '..'))
        # Otherwise do the same than on Unix/Linux

    elif is_android():
        return os.path.abspath(os.path.join(unicode(os.environ['ANDROID_PRIVATE']), u'lib/python2.7/site-packages'))

    this_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    return '/usr/share/tribler' if this_dir.startswith('/usr/lib') else this_dir


#
# install_dir.py ends here
