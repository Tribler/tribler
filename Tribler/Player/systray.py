# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import textwrap
import time
from traceback import print_exc
import wx

from Tribler.Core.API import *
from Tribler.Plugin.defs import *


class PlayerTaskBarIcon(wx.TaskBarIcon):

    def __init__(self, wxapp, iconfilename):
        wx.TaskBarIcon.__init__(self)
        self.wxapp = wxapp

        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconfilename, wx.BITMAP_TYPE_ICO)
        self.icon = self.icons.GetIcon(wx.Size(-1, -1))

        self.Bind(wx.EVT_TASKBAR_LEFT_UP, self.OnLeftClicked)

        if sys.platform != "darwin":
            # Mac already has the right icon set at startup
            self.SetIcon(self.icon, self.wxapp.appname)
        else:
            menuBar = wx.MenuBar()

            # Setting up the file menu.
            filemenu = wx.Menu()
            item = filemenu.Append(-1, 'E&xit', 'Terminate the program')
            self.Bind(wx.EVT_MENU, self.OnExit, item)

            wx.App.SetMacExitMenuItemId(item.GetId())

    def OnExit(self, e):
        self.wxapp.ExitMainLoop()
        # Close the frame.

    def CreatePopupMenu(self):
        menu = wx.Menu()

        mi = menu.Append(-1, "Options...")
        self.Bind(wx.EVT_MENU, self.OnOptions, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1, "Exit")
        self.Bind(wx.EVT_MENU, self.OnExitClient, id=mi.GetId())
        return menu

    def OnOptions(self, event=None):
        # print >>sys.stderr,"PlayerTaskBarIcon: OnOptions"
        dlg = PlayerOptionsDialog(self.wxapp, self.icons)
        ret = dlg.ShowModal()
        # print >>sys.stderr,"PlayerTaskBarIcon: Dialog returned",ret
        dlg.Destroy()

    def OnExitClient(self, event=None):
        # print >>sys.stderr,"PlayerTaskBarIcon: OnExitClient"
        self.wxapp.ExitMainLoop()

    def set_icon_tooltip(self, txt):
        if sys.platform == "darwin":
            # no taskbar tooltip on OS/X
            return

        self.SetIcon(self.icon, txt)

    def OnLeftClicked(self, event=None):
        import webbrowser
        url = 'http://127.0.0.1:' + str(self.wxapp.httpport) +URLPATH_WEBIF_PREFIX
        webbrowser.open_new_tab(url)


class PlayerOptionsDialog(wx.Dialog):

    def __init__(self, wxapp, icons):
        self.wxapp = wxapp
        self.icons = icons
        self.port = None

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, None, -1, self.wxapp.appname + ' Options', size=(400, 200), style=style)
        self.SetIcons(self.icons)

        mainbox = wx.BoxSizer(wx.VERTICAL)

        aboutbox = wx.BoxSizer(wx.VERTICAL)
        aboutlabel1 = wx.StaticText(self, -1, self.wxapp.appname + ' is a product of the P2P-Next project')
        aboutlabel2 = wx.StaticText(self, -1, 'Visit us at www.p2p-next.org!')
        aboutbox.Add(aboutlabel1, 1, wx.EXPAND | wx.LEFT |wx.RIGHT, 5)
        aboutbox.Add(aboutlabel2, 1, wx.EXPAND | wx.LEFT |wx.RIGHT, 5)

        uploadrate = self.wxapp.get_playerconfig('total_max_upload_rate')

        uploadratebox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, -1, 'Max upload to others (KB/s)')
        self.uploadratectrl = wx.TextCtrl(self, -1, str(uploadrate))
        uploadratebox.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        uploadratebox.Add(self.uploadratectrl)

        buttonbox2 = wx.BoxSizer(wx.HORIZONTAL)
        advbtn = wx.Button(self, -1, 'Advanced...')
        buttonbox2.Add(advbtn, 0, wx.ALL, 5)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, 'OK')
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
        applybtn = wx.Button(self, -1, 'Apply')
        buttonbox.Add(applybtn, 0, wx.ALL, 5)

        mainbox.Add(aboutbox, 1, wx.ALL, 5)
        mainbox.Add(uploadratebox, 1, wx.EXPAND | wx.ALL, 5)
        mainbox.Add(buttonbox2, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)

        self.Bind(wx.EVT_BUTTON, self.OnAdvanced, advbtn)
        self.Bind(wx.EVT_BUTTON, self.OnOK, okbtn)
        # self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelbtn)
        self.Bind(wx.EVT_BUTTON, self.OnApply, applybtn)
        # self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def OnOK(self, event=None):
        self.OnApply(event)
        self.EndModal(wx.ID_OK)

    # def OnCancel(self,event = None):
    #    self.EndModal(wx.ID_CANCEL)

    def OnApply(self, event=None):
        print >>sys.stderr, "PlayerOptionsDialog: OnApply", self.port

        if self.port is not None:
            session = self.wxapp.s
            state_dir = session.get_state_dir()
            cfgfilename = Session.get_default_config_filename(state_dir)
            scfg = SessionStartupConfig.load(cfgfilename)

            scfg.set_listen_port(self.port)
            print >>sys.stderr, "PlayerOptionsDialog: OnApply: Saving SessionStartupConfig to", cfgfilename
            scfg.save(cfgfilename)

        uploadrate = int(self.uploadratectrl.GetValue())
        # Updates value for global rate limiter too
        self.wxapp.set_playerconfig('total_max_upload_rate', uploadrate)
        self.wxapp.save_playerconfig()

        if self.port is not None and self.port != self.wxapp.s.get_listen_port():
            dlg = wx.MessageDialog(None, "The SwarmPlugin will now exit to change the port. Reload the Web page to restart it", self.wxapp.appname + " Restart", wx.OK |wx.ICON_INFORMATION)
            result = dlg.ShowModal()
            dlg.Destroy()
            self.wxapp.OnExit()
            # F*cking wx won't exit. Die
            os._exit(1)

    def OnAdvanced(self, event=None):

        if self.port is None:
            self.port = self.wxapp.s.get_listen_port()
        # destdir = self.wxapp.s.get_dest_dir()

        dlg = PlayerAdvancedOptionsDialog(self.icons, self.port, self.wxapp)
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            self.port = dlg.get_port()
        dlg.Destroy()


class PlayerAdvancedOptionsDialog(wx.Dialog):

    def __init__(self, icons, port, wxapp):
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER  # TODO: Add OK+Cancel
        wx.Dialog.__init__(self, None, -1, 'SwarmPlugin Advanced Options', size=(400, 200), style=style)
        self.wxapp = wxapp

        self.SetIcons(icons)

        mainbox = wx.BoxSizer(wx.VERTICAL)

        portbox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, -1, 'Port')
        self.portctrl = wx.TextCtrl(self, -1, str(port))
        portbox.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        portbox.Add(self.portctrl)

        button2box = wx.BoxSizer(wx.HORIZONTAL)
        clearbtn = wx.Button(self, -1, 'Clear disk cache and exit')
        button2box.Add(clearbtn, 0, wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnClear, clearbtn)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, 'OK')
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)

        mainbox.Add(portbox, 1, wx.EXPAND | wx.ALL, 5)
        mainbox.Add(button2box, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)

    def get_port(self):
        return int(self.portctrl.GetValue())

    def OnClear(self, event=None):
        self.wxapp.clear_session_state()
