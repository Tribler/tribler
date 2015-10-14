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


def patch_crypto_be_discovery():

    """
    Monkey patches cryptography's backend detection.
    Objective: support pyinstaller freezing.
    """

    # Just do the monkeypatching if running on a windows installer version.
    if sys.platform == 'win32' and sys.argv[0].endswith("tribler.exe"):

        from cryptography.hazmat import backends

        try:
            from cryptography.hazmat.backends.commoncrypto.backend import backend as be_cc
        except ImportError:
            be_cc = None

        try:
            from cryptography.hazmat.backends.openssl.backend import backend as be_ossl
        except ImportError:
            be_ossl = None

        backends._available_backends_list = [
            be for be in (be_cc, be_ossl) if be is not None
        ]

#
# hacks.py ends here
