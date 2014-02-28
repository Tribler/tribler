# Written by Arno Bakker
# see LICENSE.txt for license information
#
# GUITaskQueue is a server that executes tasks on behalf of the GUI that are too
# time consuming to be run by the actual GUI Thread (MainThread). Note that
# you still need to delegate the actual updating of the GUI to the MainThread via
# wx.CallAfter
#

from Tribler.Core.Misc.Singleton import Singleton
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue


class GUITaskQueue(Singleton, TimedTaskQueue):

    def __init__(self):
        super(GUITaskQueue, self).__init__(nameprefix="GUITaskQueue")
