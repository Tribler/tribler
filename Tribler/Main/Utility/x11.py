# x11.py ---
#
# Filename: x11.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Fri Jul  8 12:52:16 2016 (+0200)

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

import os
import sys
import logging


logger = logging.getLogger(__name__)


def initialize_x11_threads():
    if sys.platform == 'linux2' and os.environ.get("TRIBLER_INITTHREADS", "true").lower() == "true":
        for module in ['wx', 'wxversion', 'Tribler.vlc', 'vlc']:
            assert module not in sys.modules, "Called initialize_x11_threads after importing X related module: %s" % module
        try:
            import ctypes
            x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
            if not x11.XInitThreads():
                logger.error("Failed to initialize XInitThreads")
            os.environ["TRIBLER_INITTHREADS"] = "False"
        except OSError as e:
            logger.error("Failed to call XInitThreads '%s'", str(e))
        except Exception as e:
            logger.exception("Failed to call xInitThreads: '%s'", repr(e))


#
# x11.py ends here
