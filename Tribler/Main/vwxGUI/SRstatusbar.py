# Written by Niels Zeilemaker
import wx
import os

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.widgets import settingsButton, NativeIcon, TransparentText as StaticText, HorizontalGauge
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler
from Tribler.Core.simpledefs import UPLOAD, DOWNLOAD

DEBUG = False

class SRstatusbar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, style = wx.ST_SIZEGRIP)
        self.SetFieldsCount(5)
        self.SetStatusStyles([wx.SB_FLAT, wx.SB_FLAT, wx.SB_FLAT, wx.SB_FLAT, wx.SB_FLAT])
        
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.library_manager = self.guiutility.library_manager
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.ff_checkbox = wx.CheckBox(self, -1, 'Family filter', style=wx.ALIGN_RIGHT)
        self.ff_checkbox.Bind(wx.EVT_CHECKBOX, self.OnCheckbox)
        self.ff_checkbox.SetValue(self.guiutility.getFamilyFilter())
        
        self.speed_down_icon = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        self.speed_down_sbmp = wx.StaticBitmap(self, -1, self.speed_down_icon) 
        self.speed_down      = StaticText(self, -1, '', style = wx.ST_NO_AUTORESIZE)
        self.speed_down.Bind(wx.EVT_RIGHT_UP, self.OnDownloadPopup)
        self.speed_up_icon   = self.speed_down_icon.ConvertToImage().Rotate90().Rotate90().ConvertToBitmap()
        self.speed_up_sbmp   = wx.StaticBitmap(self, -1, self.speed_up_icon)
        self.speed_up        = StaticText(self, -1, '', style = wx.ST_NO_AUTORESIZE)
        self.speed_up.Bind(wx.EVT_RIGHT_UP, self.OnUploadPopup)

        self.searchConnectionImages = ['progressbarEmpty.png', 'progressbarFull.png']
        self.searchConnectionImages = [os.path.join(self.guiutility.vwxGUI_path, 'images', image) for image in self.searchConnectionImages]
        self.searchConnectionImages = [wx.Bitmap(image, wx.BITMAP_TYPE_ANY) for image in self.searchConnectionImages]
    
        self.activityImages = ['activity.png', 'no_activity.png']
        self.activityImages = [os.path.join(self.guiutility.vwxGUI_path, 'images', image) for image in self.activityImages]
        self.activityImages = [wx.Bitmap(image, wx.BITMAP_TYPE_ANY) for image in self.activityImages]
        
        self.connection = HorizontalGauge(self, self.searchConnectionImages[0], self.searchConnectionImages[1])
        self.activity = wx.StaticBitmap(self, -1, self.activityImages[1]) 
        self.firewallStatus = settingsButton(self, size = (14,14), name = 'firewallStatus14')
        self.firewallStatus.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        self.firewallStatus.SetToolTipString('Port status unknown')
        
        self.widths = [-1, 250, 19, 19, 19]
        self.SetStatusWidths(self.widths)
        #On windows there is a resize handle which causes wx to return a width of 1 instead of 18
        self.widths[-1] += 19 - self.GetFieldRect(4).width
        self.SetStatusWidths(self.widths)
        
        self.SetTransferSpeeds(0, 0)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        
        self.library_manager.add_download_state_callback(self.RefreshTransferSpeed)
        
    def RefreshTransferSpeed(self, dslist, magnetlist):
        total_down, total_up = 0.0, 0.0
        for ds in dslist:
            total_down += ds.get_current_speed(DOWNLOAD)
            total_up += ds.get_current_speed(UPLOAD)
        self.SetTransferSpeeds(total_down*1024, total_up*1024)
            
    def SetTransferSpeeds(self, down, up):
        self.speed_down.SetLabel(self.utility.speed_format_new(down))
        self.speed_up.SetLabel(self.utility.speed_format_new(up))
        self.Reposition()
        
    def OnDownloadPopup(self, event):
        menu = wx.Menu()
        curr_valdown = self.utility.getMaxDown()
        
        #values = ['75', '300', '600']
        values = self.utility.round_range(int(curr_valdown)) if curr_valdown.isdigit() else range(0, 1000, 100)
        values = map(str, values)
        if curr_valdown.isdigit() and curr_valdown not in values:
            values.append(curr_valdown)
            values.sort(cmp=lambda x, y: cmp(int(x), int(y)))
        values.append('unlimited')
        
        for valdown in values:
            itemid = wx.NewId()        
            menu.AppendRadioItem(itemid, str(valdown))
            menu.Bind(wx.EVT_MENU, lambda x, valdown=valdown: self.utility.setMaxDown(valdown), id=itemid)
            menu.Check(itemid, curr_valdown == str(valdown))
            
        self.speed_down.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        self.speed_down.Layout()
        
    def OnUploadPopup(self, event):
        menu = wx.Menu()
        curr_valup = self.utility.getMaxUp()
        
        #values = ['0', '50', '100']
        values = self.utility.round_range(int(curr_valup)) if curr_valup.isdigit() else range(0, 1000, 100)
        values = map(str, values)
        if curr_valup.isdigit() and curr_valup not in values:
            values.append(curr_valup)
            values.sort(cmp=lambda x, y: cmp(int(x), int(y)))
        values.append('unlimited')
            
        for valup in values:
            itemid = wx.NewId()        
            menu.AppendRadioItem(itemid, str(valup))
            menu.Bind(wx.EVT_MENU, lambda x, valup=valup: self.utility.setMaxUp(valup), id=itemid)
            menu.Check(itemid, curr_valup == str(valup))

        self.speed_up.PopupMenu(menu, event.GetPosition())
        menu.Destroy()
        self.speed_up.Layout()
    
    def OnCheckbox(self, event):
        checkbox = event.GetEventObject()
        checkbox.Enable(False)
        wx.CallLater(1000, checkbox.Enable, True)
        
        wx.CallLater(100, self.__toggleFF, event.GetEventObject().GetValue())
        
    def __toggleFF(self, newvalue):
        if newvalue != self.guiutility.getFamilyFilter():
            self.guiutility.toggleFamilyFilter(newvalue)

            def db_callback():
                self.uelog.addEvent(message="SRstatusbar: user toggled family filter", type = 2)
            startWorker(None, db_callback, retryOnBusy=True)
            
    def SetConnections(self, connectionPercentage, totalConnections):
        self.connection.SetPercentage(connectionPercentage)
        self.connection.SetToolTipString('Connected to %d peers'%totalConnections)
            
    def onReachable(self,event=None):
        if not self.guiutility.firewall_restart:
            self.firewallStatus.setSelected(2)
            self.firewallStatus.SetToolTipString('Port is working')
    
    def IsReachable(self):
        if not self.guiutility.firewall_restart:
            return self.firewallStatus.getSelected() == 2
        return False
    
    def onActivity(self, msg):
        def revert():
            self.activity.SetBitmap(self.activityImages[1])
            self.activity.Refresh()
        
        self.activity.SetBitmap(self.activityImages[0])
        self.activity.Refresh()
        self.activity.SetToolTipString(msg)
        wx.CallLater(200, revert)
    
    def format_bytes(self, bytes):
        if bytes < 1000:
            return '%d B' % bytes
        if bytes < 1024:
            return '%1.1f KB' % (bytes/1024.0)
        if bytes < 1022796:
            return '%d KB' % (bytes//1024)
        if bytes < 1048576:
            return '%1.1f MB' % (bytes//1048576.0)
        if bytes < 1047527425:
            return '%d MB' % (bytes//1048576)
        if bytes < 1073741824:
            return '%1.1f GB' % (bytes//1073741824.0)
        return '%d GB' % (bytes//1073741824)
    
    def OnSize(self, event):
        self.Reposition()
    
    def Reposition(self):
        self.Freeze()
        
        rect = self.GetFieldRect(0)
        self.ff_checkbox.SetPosition((rect.x+2, rect.y+2))
        self.ff_checkbox.SetSize((-1, rect.height-4))
        
        rect = self.GetFieldRect(1)
        x = rect.x+rect.width-15
        for control in reversed([self.speed_down_sbmp, self.speed_down, self.speed_up_sbmp, self.speed_up]):
            x -= control.GetSize()[0]+10
            y = (rect.height - control.GetSize()[1])/2 if isinstance(control, wx.StaticBitmap) else rect.y+2
            control.SetPosition((x, y+1))
        
        rect = self.GetFieldRect(2)
        size = self.connection.GetSize()
        yAdd = (rect.height - size[1])/2
        xAdd = (rect.width - size[0])/2
        self.connection.SetPosition((rect.x+xAdd, rect.y+yAdd))

        rect = self.GetFieldRect(3)        
        size = self.activity.GetSize()
        yAdd = (rect.height - size[1])/2
        xAdd = (rect.width - size[0])/2
        self.activity.SetPosition((rect.x+xAdd, rect.y+yAdd))
        
        rect = self.GetFieldRect(4)
        size = self.firewallStatus.GetSize()
        yAdd = (rect.height - size[1])/2
        xAdd = (rect.width - size[0])/2
        self.firewallStatus.SetPosition((rect.x+xAdd, rect.y+yAdd))
        
        self.sizeChanged = False
        self.Thaw()