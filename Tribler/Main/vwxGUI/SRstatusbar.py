# Written by Niels Zeilemaker
import wx

from Tribler.Core.simpledefs import UPLOAD, DOWNLOAD

from Tribler.Main.vwxGUI import warnWxThread, forceWxThread
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.widgets import HorizontalGauge, ActionButton

from Tribler.Main.Utility.utility import size_format, round_range, speed_format


class SRstatusbar(wx.StatusBar):

    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, style=wx.ST_SIZEGRIP)

        # On Linux/OS X the resize handle and icons overlap, therefore we add an extra field.
        # On Windows this field is automatically set to 1 when the wx.ST_SIZEGRIP is set.
        self.SetFieldsCount(7)
        self.SetStatusStyles([wx.SB_FLAT] * 7)
        self.SetStatusWidths([-1, 250, 50, 19, 19, 19, 19])

        self._gui_image_manager = GuiImageManager.getInstance()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.library_manager = self.guiutility.library_manager

        self.ff_checkbox = wx.CheckBox(self, -1, 'Family filter', style=wx.ALIGN_RIGHT)
        self.ff_checkbox.Bind(wx.EVT_CHECKBOX, self.OnCheckbox)
        self.ff_checkbox.SetValue(self.guiutility.getFamilyFilter())

        self.speed_down_icon = self._gui_image_manager.getBitmap(self, u"arrow", self.GetBackgroundColour(), state=0)
        self.speed_down_sbmp = wx.StaticBitmap(self, -1, self.speed_down_icon)
        self.speed_down_sbmp.Bind(wx.EVT_RIGHT_UP, self.OnDownloadPopup)
        self.speed_down = wx.StaticText(self, -1, '')
        self.speed_down.Bind(wx.EVT_RIGHT_UP, self.OnDownloadPopup)
        self.speed_up_icon = self.speed_down_icon.ConvertToImage().Rotate90().Rotate90().ConvertToBitmap()
        self.speed_up_sbmp = wx.StaticBitmap(self, -1, self.speed_up_icon)
        self.speed_up_sbmp.Bind(wx.EVT_RIGHT_UP, self.OnUploadPopup)
        self.speed_up = wx.StaticText(self, -1, '')
        self.speed_up.Bind(wx.EVT_RIGHT_UP, self.OnUploadPopup)

        self.free_space_icon = self._gui_image_manager.getImage(u"drive.png")
        self.free_space_sbmp = wx.StaticBitmap(self, -1, self.free_space_icon)
        self.free_space = wx.StaticText(self, -1, '')

        self.searchConnectionImages = [u"progressbarEmpty.png", u"progressbarFull.png"]
        self.searchConnectionImages = [self._gui_image_manager.getImage(image) for image in self.searchConnectionImages]

        self.activityImages = [u"statusbar_activity.png", u"statusbar_noactivity.png"]
        self.activityImages = [self._gui_image_manager.getImage(image) for image in self.activityImages]

        self.connection = HorizontalGauge(self, self.searchConnectionImages[0], self.searchConnectionImages[1])
        self.activity = wx.StaticBitmap(self, -1, self.activityImages[1])
        self.activity_timer = None
        self.channelconnections = 0

        self.bmp_firewall_warning = self._gui_image_manager.getImage(u"statusbar_warning.png")
        self.bmp_firewall_ok = self._gui_image_manager.getImage(u"statusbar_ok.png")
        self.firewallStatus = ActionButton(self, -1, self.bmp_firewall_warning)
        self.firewallStatus.SetSize((16, 16))
        self.firewallStatus.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        self.firewallStatus.SetToolTipString('Port status unknown')
        self.firewallStatus.Enable(False)
        self.firewallStatus.SetBitmapDisabled(self.bmp_firewall_warning)

        self.SetTransferSpeeds(0, 0)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.library_manager.add_download_state_callback(self.RefreshTransferSpeed)

    @forceWxThread
    def RefreshFreeSpace(self, space):
        if space >= 0:
            space_str = size_format(space, truncate=1)
            space_label = space_str.replace(' ', '')
            space_tooltip = 'You currently have %s of disk space available on your default download location.' % space_str
            self.free_space.SetLabel(space_label)
            self.free_space.SetToolTipString(space_tooltip)
            self.free_space.Show(True)
            self.free_space_sbmp.SetToolTipString(space_tooltip)
            self.free_space_sbmp.Show(True)
        else:
            self.free_space.Show(False)
            self.free_space_sbmp.Show(False)
        self.Reposition()

    def RefreshTransferSpeed(self, dslist, magnetlist):
        if not self:
            return

        total_down, total_up = 0.0, 0.0
        for ds in dslist:
            total_down += ds.get_current_speed(DOWNLOAD)
            total_up += ds.get_current_speed(UPLOAD)
        self.SetTransferSpeeds(total_down, total_up)

    @warnWxThread
    def SetTransferSpeeds(self, down, up):
        self.speed_down.SetLabel(speed_format(down))
        self.speed_up.SetLabel(speed_format(up))
        self.Reposition()

    def SetGlobalMaxSpeed(self, direction, value):
        if direction in [UPLOAD, DOWNLOAD]:
            if direction == UPLOAD:
                self.utility.write_config('maxuploadrate', value)
                self.guiutility.utility.session.set_max_upload_speed(value)
            else:
                self.utility.write_config('maxdownloadrate', value)
                self.guiutility.utility.session.set_max_download_speed(value)

    def GetSpeedChoices(self, value):
        values = round_range(max(0, value)) if value != 0 else range(0, 1000, 100)
        values = [value or -1 for value in values]
        if value != 0 and value not in values:
            values.append(value)
            values.sort()
        values.append(0)
        return [('unlimited' if value == 0 else ('0' if value == -1 else str(value)), value) for value in values]

    def OnDownloadPopup(self, event):
        menu = wx.Menu()
        current = self.utility.read_config('maxdownloadrate')
        value_tuples = self.GetSpeedChoices(current)

        for value_str, value in value_tuples:
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, value_str)
            menu.Bind(wx.EVT_MENU, lambda x, v=value: self.SetGlobalMaxSpeed(DOWNLOAD, v), id=itemid)
            menu.Check(itemid, current == value)

        self.speed_down.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        self.speed_down.Layout()

    def OnUploadPopup(self, event):
        menu = wx.Menu()
        current = self.utility.read_config('maxuploadrate')
        value_tuples = self.GetSpeedChoices(current)

        for value_str, value in value_tuples:
            itemid = wx.NewId()
            menu.AppendRadioItem(itemid, value_str)
            menu.Bind(wx.EVT_MENU, lambda x, v=value: self.SetGlobalMaxSpeed(UPLOAD, v), id=itemid)
            menu.Check(itemid, current == value)

        self.speed_up.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        self.speed_up.Layout()

    def OnCheckbox(self, event):
        checkbox = event.GetEventObject()
        checkbox.Enable(False)
        wx.CallLater(1000, checkbox.Enable, True)

        wx.CallLater(100, self.__toggleFF, event.GetEventObject().GetValue())

    @warnWxThread
    def __toggleFF(self, newvalue):
        if newvalue != self.guiutility.getFamilyFilter():
            self.guiutility.toggleFamilyFilter(newvalue)

    @warnWxThread
    def SetConnections(self, connectionPercentage, totalConnections, channelConnections):
        self.connection.SetPercentage(connectionPercentage)
        self.connection.SetToolTipString('Connected to %d peers' % totalConnections)
        self.channelconnections = channelConnections

    def GetConnections(self):
        return self.connection.GetPercentage()

    def GetChannelConnections(self):
        return self.channelconnections

    @warnWxThread
    def onReachable(self, event=None):
        if not self.guiutility.firewall_restart:
            self.firewallStatus.SetBitmapLabel(self.bmp_firewall_ok)
            self.firewallStatus.SetBitmapDisabled(self.bmp_firewall_ok)
            self.firewallStatus.SetToolTipString('Port is working')

    @warnWxThread
    def IsReachable(self):
        if not self.guiutility.firewall_restart:
            return self.firewallStatus.GetBitmapLabel() == self.bmp_firewall_ok
        return False

    @warnWxThread
    def onActivity(self, msg):
        if self.activity_timer:
            self.activity_timer.Stop()

        def revert():
            if not self:
                return
            self.activity.SetBitmap(self.activityImages[1])
            self.activity.Refresh()

        self.activity.SetBitmap(self.activityImages[0])
        self.activity.Refresh()
        self.activity.SetToolTipString(msg)
        self.activity_timer = wx.CallLater(300, revert)

    def OnSize(self, event):
        self.Reposition()

    def Reposition(self):
        self.Freeze()

        rect = self.GetFieldRect(0)
        self.ff_checkbox.SetPosition((rect.x + 2, rect.y + 2))
        self.ff_checkbox.SetSize((-1, rect.height - 4))

        rect = self.GetFieldRect(1)
        x = rect.x + rect.width - 15
        for control in reversed([self.speed_down_sbmp, self.speed_down, self.speed_up_sbmp, self.speed_up]):
            spacer = 10 if not isinstance(control, wx.StaticBitmap) else 7
            x -= control.GetSize()[0] + spacer
            yAdd = (rect.height - control.GetSize()[1]) / 2
            control.SetPosition((x, rect.y + yAdd))

        rect = self.GetFieldRect(2)
        x = rect.x + rect.width
        for control in [self.free_space, self.free_space_sbmp]:
            size = control.GetSize()
            yAdd = (rect.height - size[1]) / 2
            x -= size[0] + 5
            control.SetPosition((x, rect.y + yAdd))

        rect = self.GetFieldRect(3)
        size = self.connection.GetSize()
        yAdd = (rect.height - size[1]) / 2
        xAdd = (rect.width - size[0]) / 2
        self.connection.SetPosition((rect.x + xAdd, rect.y + yAdd))

        rect = self.GetFieldRect(4)
        size = self.activity.GetSize()
        yAdd = (rect.height - size[1]) / 2
        xAdd = (rect.width - size[0]) / 2
        self.activity.SetPosition((rect.x + xAdd, rect.y + yAdd))

        rect = self.GetFieldRect(5)
        size = self.firewallStatus.GetSize()
        yAdd = (rect.height - size[1]) / 2
        xAdd = (rect.width - size[0]) / 2
        self.firewallStatus.SetPosition((rect.x + xAdd, rect.y + yAdd))

        self.sizeChanged = False
        self.Thaw()
