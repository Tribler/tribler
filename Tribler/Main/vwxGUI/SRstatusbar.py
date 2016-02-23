# Written by Niels Zeilemaker
import sys
import wx

from Tribler.Core.simpledefs import UPLOAD, DOWNLOAD

from Tribler.Main.vwxGUI import warnWxThread, forceWxThread
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.widgets import HorizontalGauge, ActionButton

from Tribler.Main.Utility.utility import size_format, round_range, speed_format

from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics

class SRstatusbar(wx.StatusBar):

    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, style=wx.ST_SIZEGRIP)

        self._gui_image_manager = GuiImageManager.getInstance()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.library_manager = self.guiutility.library_manager

        self.ff_checkbox = wx.CheckBox(self, -1, 'Family filter', style=wx.ALIGN_RIGHT)
        self.ff_checkbox.Bind(wx.EVT_CHECKBOX, self.OnCheckbox)
        self.ff_checkbox.SetValue(self.guiutility.getFamilyFilter())

        self.tunnel_contrib = wx.StaticText(self, -1, '')
        self.tunnel_contrib.SetToolTipString('Total Anonymity Contribution')
        self.tunnel_contribNet = wx.StaticText(self, -1, '')
        self.tunnel_contribNet.SetToolTipString('Anonymity Contribution Balance')
        
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

        # On Linux/OS X the resize handle and icons overlap, therefore we add an extra field.
        # On Windows this field is automatically set to 1 when the wx.ST_SIZEGRIP (parent class constructor) is set.
        self.fields = [
                  (-1,   wx.SB_FLAT, [self.ff_checkbox]),
                  (100,  wx.SB_FLAT, [self.tunnel_contrib, self.tunnel_contribNet]),
                  (200,  wx.SB_FLAT, [self.speed_down_sbmp, self.speed_down, self.speed_up_sbmp, self.speed_up]),
                  (75,   wx.SB_FLAT, [self.free_space_sbmp, self.free_space]),
                  (19,   wx.SB_FLAT, [self.connection]),
                  (19,   wx.SB_FLAT, [self.activity]),
                  (19,   wx.SB_FLAT, [self.firewallStatus]),
                  (19,   wx.SB_FLAT, [])]
        self.SetFieldsCount(len(self.fields))
        self.SetStatusWidths([field[0] for field in self.fields])
        self.SetStatusStyles([field[1] for field in self.fields])

        self.SetTransferSpeeds(0, 0)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.library_manager.add_download_state_callback(self.RefreshTransferSpeed)

    def UpdateTunnelContrib(self):
        totalup = (sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_BYTES_SENT].values()) +
                   sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_RELAY_BYTES_SENT].values()) +
                   sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT].values()))
        totaldown = (sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_BYTES_RECEIVED].values()) +
                     sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_RELAY_BYTES_RECEIVED].values()) +
                     sum(_barter_statistics.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED].values()))
        self.SetTunnelContrib(totalup + totaldown, totalup - totaldown)

    @warnWxThread
    def SetTunnelContrib(self, totalcontrib, netcontrib):
        self.tunnel_contrib.SetLabel('Total: %s' % size_format(totalcontrib, truncate=2))
        self.tunnel_contribNet.SetLabel('Balance: %s' % size_format(netcontrib, truncate=2))
        self.Reposition()

    @forceWxThread
    def RefreshFreeSpace(self, space):
        if space >= 0:
            space_str = size_format(space, truncate=1)
            space_label = space_str.replace(' ', '')
            space_tooltip = 'You currently have %s of disk space available on your default download location.' % space_str
            self.free_space.SetLabel(space_label)
            self.free_space.Show(True)
            self.free_space_sbmp.Show(True)
            # TODO martijn: we disabled some tooltips that are periodically updated on OS X.
            # There seems to be a bug (in wx3) where the tooltip would always show when being updated.
            if sys.platform != 'darwin':
                self.free_space_sbmp.SetToolTipString(space_tooltip)
                self.free_space.SetToolTipString(space_tooltip)
        else:
            self.free_space.Show(False)
            self.free_space_sbmp.Show(False)
        self.Reposition()

    def RefreshTransferSpeed(self, dslist, magnetlist):
        if not self:
            return

        self.UpdateTunnelContrib()
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
        if sys.platform != 'darwin':
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
        if sys.platform != 'darwin':
            self.activity.SetToolTipString(msg)
        self.activity_timer = wx.CallLater(300, revert)

    def OnSize(self, event):
        self.Reposition()

    def Reposition(self):
        self.Freeze()

        # default spacing rules
        #  - field has 1 control, center it
        #  - field has -1 width (fill), skip it
        #  - starting from the right align all controls with 10 spacing between them, or 7 if it it a bitmap
        for field_index, field in enumerate(self.fields):
            if field[0] == -1:
                continue
            rect = self.GetFieldRect(field_index)
            if len(field[2]) == 1:
                control = field[2][0]
                control.SetPosition((
                                     rect.x + (rect.width - control.GetSize()[0])/2,
                                     rect.y + (rect.height - control.GetSize()[1])/2))
            else:
                x = rect.x + rect.width
                for control in reversed(field[2]):
                    spacer = 10 if not isinstance(control, wx.StaticBitmap) else 7
                    x -= control.GetSize()[0] + spacer
                    control.SetPosition((x, rect.y + (rect.height - control.GetSize()[1])/2))

        # any other layout work not covered by the default rules should happen here.
        rect = self.GetFieldRect(0)
        self.ff_checkbox.SetPosition((rect.x + 2, rect.y + 2))
        self.ff_checkbox.SetSize((-1, rect.height - 4))

        self.sizeChanged = False
        self.Thaw()
