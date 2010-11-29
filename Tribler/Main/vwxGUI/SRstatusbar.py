# Written by Richard Gwin
import wx.html
import sys
import os

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import settingsButton

DEBUG = False

class SRstatusbar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, style = wx.ST_SIZEGRIP)
        self.SetFieldsCount(2)
        self.SetStatusStyles([wx.SB_FLAT, wx.SB_FLAT])
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        
        self.srPanel = wx.Panel(self)
        srlabel = wx.StaticText(self.srPanel, -1, "Sharing Reputation:")
        self.sr = wx.StaticText(self.srPanel)
        help = wx.StaticBitmap(self.srPanel, -1, wx.Bitmap(os.path.join(self.utility.getPath(), LIBRARYNAME, "Main", "vwxGUI", "images" , "help.png"),wx.BITMAP_TYPE_ANY))
        help.Bind(wx.EVT_LEFT_UP, self.helpClick)
        self.updown = wx.StaticText(self.srPanel)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(srlabel, 0, wx.RIGHT|wx.LEFT|wx.ALIGN_CENTER_VERTICAL, 5)
        hSizer.Add(self.sr, 0, wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 10)
        hSizer.Add(help, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        hSizer.Add(self.updown, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        self.srPanel.SetSizer(hSizer)
        
        self.firewallStatus = settingsButton(self, size = (14,14), name = 'firewallStatus14')
        
        self.widths = [-1, 19]
        self.SetStatusWidths(self.widths)
        #On windows there is a resize handle which causes wx to return a width of 1 instead of 18
        self.widths[1] += 19 - self.GetFieldRect(1).width
        self.SetStatusWidths(self.widths)
        
        self.Reposition()
        self.Bind(wx.EVT_SIZE, self.OnSize)
 
    def helpClick(self,event=None):
        dlg = wx.Dialog(None, -1, self.utility.lang.get('sharing_reputation_information_title'), style=wx.DEFAULT_DIALOG_STYLE, size=(400,200))
        dlg.SetBackgroundColour(wx.WHITE)

        sizer = wx.FlexGridSizer(2,2)
        
        icon = wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX))
        sizer.Add(icon, 0, wx.TOP, 10)
        
        hwin = wx.html.HtmlWindow(dlg, -1, size = (350, 130))
        hwin.SetPage(self.utility.lang.get('sharing_reputation_information_message'))
        sizer.Add(hwin)
        
        sizer.Add((10,0))
        
        btn = wx.Button(dlg, wx.ID_OK, 'Ok')
        sizer.Add(btn, 0, wx.ALIGN_RIGHT, 5)
        
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        dlg.SetSizerAndFit(border)
        dlg.ShowModal()
        dlg.Destroy()
        
    def set_reputation(self, reputation, down, up):
        if DEBUG:
            print >> sys.stderr , "SRstatusbar: My Reputation",reputation
            
        changed = False
        if reputation < -0.33:
            newColor = (255,51,0)
            newLabel = "Poor"
        elif reputation < 0.33:
            newColor = wx.BLACK
            newLabel = "Average"
        else:
            newColor = (0,80,120)
            newLabel = "Good"
        
        if self.sr.GetLabel() != newLabel:
            self.sr.SetLabel(newLabel)
            self.sr.SetForegroundColour(newColor)
            changed = True
        
        newLabel = self.format_bytes(down * 1024.0) + ' Down ' + self.format_bytes(up * 1024.0) + ' Up'
        if self.updown.GetLabel() != newLabel:
            self.updown.SetLabel(newLabel)
            changed = True
            
        if changed:
            self.Reposition()
        
    def onReachable(self,event=None):
        if not self.guiUtility.firewall_restart:
            self.firewallStatus.setSelected(2)
            self.firewallStatus.SetToolTipString('Port is working')
    
    def IsReachable(self):
        if not self.guiUtility.firewall_restart:
            return self.firewallStatus.getSelected() == 2
        return False
    
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
        self.srPanel.Layout()
        self.srPanel.SetPosition((rect.x, rect.y))
        bestWidth = self.srPanel.GetBestSize()[0]
        self.srPanel.SetSize((bestWidth, rect.height))
        
        rect = self.GetFieldRect(1)
        size = self.firewallStatus.GetSize()
        yAdd = (rect.height - size[1])/2
        self.firewallStatus.SetPosition((rect.x, rect.y+yAdd))
        self.sizeChanged = False
        
        self.Thaw()