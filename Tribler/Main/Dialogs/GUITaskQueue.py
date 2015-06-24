# Written by Arno Bakker
# see LICENSE.txt for license information
#
# GUITaskQueue is a server that executes tasks on behalf of the GUI that are too
# time consuming to be run by the actual GUI Thread (MainThread). Note that
# you still need to delegate the actual updating of the GUI to the MainThread via
# wx.CallAfter
#

from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue


class GUITaskQueue(TimedTaskQueue):

    __single = None

    def __init__(self):
        if GUITaskQueue.__single:
            raise RuntimeError("GUITaskQueue is singleton")
        GUITaskQueue.__single = self

        TimedTaskQueue.__init__(self, nameprefix="GUITaskQueue")

    def getInstance(*args, **kw):
        if GUITaskQueue.__single is None:
            GUITaskQueue(*args, **kw)
        return GUITaskQueue.__single
    getInstance = staticmethod(getInstance)

    @staticmethod
    def delInstance(*args, **kw):
        GUITaskQueue.__single = None

    def resetSingleton(self):
        """ For testing purposes """
        GUITaskQueue.__single = None
