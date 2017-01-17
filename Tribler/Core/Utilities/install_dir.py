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
import Tribler

from Tribler.Core.osutils import is_android, get_home_dir


def is_frozen():
    """
    Return whether we are running in a frozen environment
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        return False
    return True


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.join(os.path.dirname(Tribler.__file__), '..')
    return base_path


def get_lib_path():
    if is_frozen():
        return os.path.join(get_base_path(), 'tribler_source', 'Tribler')
    return os.path.join(get_base_path(), 'Tribler')


# This function is used from tribler.py too, but can't be there as tribler.py gets frozen into an exe on windows.
def determine_install_dir():
    # Niels, 2011-03-03: Working dir sometimes set to a browsers working dir
    # only seen on windows

    # apply trick to obtain the executable location
    # see http://www.py2exe.org/index.cgi/WhereAmI
    # Niels, 2012-01-31: py2exe should only apply to windows

    # TODO(emilon): tribler_main.py is not frozen, so I think the special
    # treatment for windows could be removed (Needs to be tested)
    if sys.platform == 'win32':
        return get_base_path()
    elif sys.platform == 'darwin':
        return get_base_path()
    elif is_android():
        return os.path.abspath(os.path.join(unicode(os.environ['ANDROID_PRIVATE']), u'lib/python2.7/site-packages'))

    this_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    return '/usr/share/tribler' if this_dir.startswith('/usr/lib') else this_dir


#
# install_dir.py ends here
