# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
from traceback import print_exc
import wx

from Tribler.Core.API import *

class PlayerTaskBarIcon(wx.TaskBarIcon):
    
    def __init__(self,wxapp,iconfilename):
        wx.TaskBarIcon.__init__(self)
        self.wxapp = wxapp
        
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconfilename,wx.BITMAP_TYPE_ICO)
        self.icon = self.icons.GetIcon(wx.Size(-1,-1))
        self.SetIcon(self.icon,'SwarmPlayer')
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        
        mi = menu.Append(-1,"Options...")
        self.Bind(wx.EVT_MENU, self.OnOptions, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1,"Exit")
        self.Bind(wx.EVT_MENU, self.OnExitClient, id=mi.GetId())
        return menu
        
    def OnOptions(self,event=None):
        print >>sys.stderr,"PlayerTaskBarIcon: OnOptions"
        dlg = PlayerOptionsDialog(self.wxapp)
        ret = dlg.ShowModal()
        #print >>sys.stderr,"PlayerTaskBarIcon: Dialog returned",ret
        dlg.Destroy()

    def OnExitClient(self,event=None):
        #print >>sys.stderr,"PlayerTaskBarIcon: OnExitClient"
        self.wxapp.ExitMainLoop()
    
    
class PlayerOptionsDialog(wx.Dialog):
    
    def __init__(self,wxapp):
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, None, -1, 'SwarmPlayer Options', size=(400,200), style=style)
        self.wxapp = wxapp

        iconpath = os.path.join(wxapp.installdir,'Tribler','Images','tribler.ico')
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconpath,wx.BITMAP_TYPE_ICO)
        self.SetIcons(self.icons)

        port = wxapp.s.get_listen_port()
        #destdir = wxapp.s.get_dest_dir()

        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        portbox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, -1, 'Port')
        self.port = wx.TextCtrl(self, -1, str(port))
        portbox.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        portbox.Add(self.port)

        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, -1, 'OK')
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        cancelbtn = wx.Button(self, -1, 'Cancel')
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
        applybtn = wx.Button(self, -1, 'Apply')
        buttonbox.Add(applybtn, 0, wx.ALL, 5)

        mainbox.Add(portbox, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)

        self.Bind(wx.EVT_BUTTON, self.OnOK, okbtn)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelbtn)
        self.Bind(wx.EVT_BUTTON, self.OnApply, applybtn)
        #self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def OnOK(self,event = None):
        self.EndModal(wx.ID_OK)
        
    def OnCancel(self,event = None):
        self.EndModal(wx.ID_CANCEL)
        
    def OnApply(self,event = None):
        print >>sys.stderr,"PlayerOptionsDialog: OnApply"
        session = self.wxapp.s
        state_dir = session.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)
        
        port = int(self.port.GetValue())
        scfg.set_listen_port(port)
        
        scfg.save(cfgfilename)
        
        # For max upload, etc. we also have to modify the runtime Session.
