# Written by Arno Bakker
# see LICENSE.txt for license information
#
# GUIServer is a server that executes tasks on behalf of the GUI that are too
# time consuming to be run by the actual GUI Thread (MainThread). Note that
# you still need to delegate the actual updating of the GUI to the MainThread via
# wx.CallAfter
#

from threading import Thread,Condition
from traceback import print_exc
from time import time

from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue

DEBUG = False

class GUIServer(TimedTaskQueue):
    
    __single = None
    
    def __init__(self):
        if GUIServer.__single:
            raise RuntimeError, "GUIServer is singleton"
        GUIServer.__single = self

        TimedTaskQueue.__init__(self)
        
    def getInstance(*args, **kw):
        if GUIServer.__single is None:
            GUIServer(*args, **kw)
        return GUIServer.__single
    getInstance = staticmethod(getInstance)

