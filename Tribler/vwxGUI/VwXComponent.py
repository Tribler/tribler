# -*- coding: iso-8859-1 -*- 

import wx
class VwXtaskBar(wx.TaskBarIcon):
    def __init__(self,win):
        self.win=win
        wx.TaskBarIcon.__init__(self)
        self.Bind(wx.EVT_TASKBAR_MOVE,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_LEFT_UP,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_RIGHT_DOWN,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK,self.VwXAllEvents)
        self.Bind(wx.EVT_TASKBAR_RIGHT_DCLICK,self.VwXAllEvents)
        self.Bind(wx.EVT_MENU,self.OnMenu,id=-1)
        
    def VwXAllEvents(self,event):
        self.win.GetEventHandler().ProcessEvent(event)
        if(event.GetEventType()==wx.wxEVT_TASKBAR_RIGHT_DOWN):
            event.Skip(True)

    def CreatePopupMenu(self):
        return self.win.VwXGetTaskBarMenu()

    def OnMenu(self,event):
        self.win.GetEventHandler().ProcessEvent(event)
