# test_torrent_store.py ---
#
# Filename: test_torrent_store.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Wed Jan 21 12:45:30 2015 (+0100)

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
from twisted.internet.task import Clock

from tempfile import mkdtemp

from Tribler.Core.torrentstore import TorrentStore
from Tribler.Core.plyveladapter import LevelDB
from Tribler.Test.test_torrent_store import TestTorrentStore, K, V


class ClockedTorrentStore(TorrentStore):
    _reactor = Clock()
    _leveldb = LevelDB

class TestTorrentStore_Plyvel(TestTorrentStore):
    pass
    

#
# test_torrent_store_plyvel.py ends here
