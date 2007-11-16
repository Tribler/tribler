# Written by Arno Bakker
# see LICENSE.txt for license information
#
# Arno, 2007-04-24: The whole doneflag may not be necessary. As we're going
# for 4.0 I won't touch the code now, TODO.
#
#
import wx
from threading import Event,currentThread

wxEVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)
    
def DELEVT_INVOKE(win):
    win.Disconnect(-1, -1, wxEVT_INVOKE)

class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        wx.PyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


class DelayedInvocation:
    def __init__(self):
        # self.doneflag must be defined by each class that inherits from this
        EVT_INVOKE(self, self.onInvoke)

    def onInvoke(self, event):
        if ((self.doneflag is not None)
            and (not self.doneflag.isSet())):
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if ((self.doneflag is not None)
            and (not self.doneflag.isSet())):
            ## Arno: I noticed a problem when the mainthread itself calls 
            ## invokeLater(), so I added this special case.
            if currentThread().getName() == 'MainThread':
                func(*args,**kwargs)
            else:
                wx.PostEvent(self, InvokeEvent(func, args, kwargs))

class DelayedEventHandler(DelayedInvocation,wx.EvtHandler):
    def __init__(self):
        wx.EvtHandler.__init__(self)
        DelayedInvocation.__init__(self)

class FlaglessDelayedInvocation:
    def __init__(self):
        EVT_INVOKE(self, self.onInvoke)

    def onInvoke(self, event):
        event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        ## Arno: I noticed a problem when the mainthread itself calls 
        ## invokeLater(), so I added this special case.
        if currentThread().getName() == 'MainThread':
            func(*args,**kwargs)
        else:
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))

class FlaglessDelayedEventHandler(FlaglessDelayedInvocation,wx.EvtHandler):
    def __init__(self):
        wx.EvtHandler.__init__(self)
        FlaglessDelayedInvocation.__init__(self)

