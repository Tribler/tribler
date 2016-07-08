# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
# see LICENSE.txt for license information
import sys
import wx
from traceback import print_exc
from Tribler.Main.Utility.utility import speed_format

try:
    import win32gui  # , win32con
    WIN32 = True
except ImportError:
    WIN32 = False

#
#
# Class : ABCTaskBarIcon
#
# Task Bar Icon
#
#


class ABCTaskBarIcon(wx.TaskBarIcon):

    def __init__(self, parent):
        wx.TaskBarIcon.__init__(self)

        self.parent = parent
        self.utility = parent.utility

        # setup a taskbar icon, and catch some events from it
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, parent.onTaskBarActivate)
        self.Bind(wx.EVT_MENU, parent.onTaskBarActivate, id=wx.NewId())

        self.updateIcon(False)

    def updateTooltip(self, download_speed=0, upload_speed=0):
        if not WIN32:
            return
        self.tooltip = "Down: %s, Up: %s" % (speed_format(download_speed), speed_format(upload_speed))
        self.SetIcon(self.icon, self.tooltip)

    def updateIcon(self, iconifying=False):
        remove = True

        if sys.platform == 'win32':
            mintray = 2
        else:
            mintray = self.utility.read_config('mintray')

        if (mintray >= 2) or ((mintray >= 1) and iconifying):
            remove = False

        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.parent.GetIcon(), "Tribler")

    def CreatePopupMenu(self):
        menu = wx.Menu()

        mi = menu.Append(-1, 'Stop All')
        self.Bind(wx.EVT_MENU, self.OnStopAll, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1, 'Restart All')
        self.Bind(wx.EVT_MENU, self.OnRestartAll, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1, '&Exit')
        self.Bind(wx.EVT_MENU, self.OnExitClient, id=mi.GetId())
        return menu

    def Notify(self, title, msg, icon):
        if WIN32 and self.IsIconInstalled():
            if not msg and title:
                msg = title
                title = ''
            try:
                self.__SetBalloonTip(self.icon.GetHandle(), title, msg, 0, icon)
                return True
            except Exception:
                pass
        return False

    def __SetBalloonTip(self, hicon, title, msg, msec, icon):
        if icon == wx.ART_INFORMATION:
            infoFlags = win32gui.NIIF_INFO
        elif icon == wx.ART_WARNING:
            infoFlags = win32gui.NIIF_WARNING
        elif icon == wx.ART_ERROR:
            infoFlags = win32gui.NIIF_ERROR
        else:
            infoFlags = 0

        lpdata = (self.__GetIconHandle(),
                  99,
                  win32gui.NIF_MESSAGE | win32gui.NIF_TIP | win32gui.NIF_INFO | win32gui.NIF_ICON,
                  0,
                  hicon,
                  '',
                  msg,
                  msec,
                  title,
                  infoFlags)
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, lpdata)

        self.SetIcon(self.icon, self.tooltip)

    def __GetIconHandle(self):
        if not hasattr(self, "_chwnd"):
            try:
                for handle in wx.GetTopLevelWindows():
                    if handle.GetWindowStyle():
                        continue
                    handle = handle.GetHandle()
                    if len(win32gui.GetWindowText(handle)) == 0:
                        self._chwnd = handle
                        break
                if not hasattr(self, "_chwnd"):
                    pass
            except:
                pass
        return self._chwnd

    def SetIcon(self, icon, tooltip=""):
        self.icon = icon
        self.tooltip = tooltip
        wx.TaskBarIcon.SetIcon(self, icon, tooltip)

    def OnStopAll(self, event=None):
        dlist = self.utility.session.get_downloads()
        for d in dlist:
            try:
                d.stop()
            except:
                print_exc()

    def OnRestartAll(self, event=None):
        dlist = self.utility.session.get_downloads()
        for d in dlist:
            try:
                d.restart()
            except:
                print_exc()

    def OnExitClient(self, event=None):
        self.parent.quit()
