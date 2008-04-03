# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import os
import wx
from traceback import print_exc
      
##############################################################
#
# Class : ABCTaskBarIcon
#
# Task Bar Icon
#
############################################################## 
class ABCTaskBarIcon(wx.TaskBarIcon):
    def __init__(self, parent):
        wx.TaskBarIcon.__init__(self)
        
        self.parent = parent
        self.utility = parent.utility
        
        self.TBMENU_RESTORE = wx.NewId()

        # setup a taskbar icon, and catch some events from it
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, parent.onTaskBarActivate)
        self.Bind(wx.EVT_MENU, parent.onTaskBarActivate, id = self.TBMENU_RESTORE)
               
        self.updateIcon(False)
        
    def updateIcon(self,iconifying = False):
        remove = True
        
        mintray = self.utility.config.Read('mintray', "int")
        if (mintray >= 2) or ((mintray >= 1) and iconifying):
            remove = False
        
        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.utility.icon, "Tribler")
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        
        mi = menu.Append(-1,self.utility.lang.get('stopall'))
        self.Bind(wx.EVT_MENU, self.OnStopAll, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1,self.utility.lang.get('restartall'))
        self.Bind(wx.EVT_MENU, self.OnRestartAll, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1,self.utility.lang.get('menuexit'))
        self.Bind(wx.EVT_MENU, self.OnExitClient, id=mi.GetId())
        return menu
        
    def OnStopAll(self,event=None):
        dlist = self.utility.session.get_downloads()
        for d in dlist:
            try:
                d.stop()
            except:
                print_exc()
    
    def OnRestartAll(self,event=None):
        dlist = self.utility.session.get_downloads()
        for d in dlist:
            try:
                d.restart()
            except:
                print_exc()

    def OnExitClient(self,event=None):
        self.parent.quit()
