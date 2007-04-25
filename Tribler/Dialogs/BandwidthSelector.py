# Written by Arno Bakker
# see LICENSE.txt for license information

import wx
import sys


class BandwidthSelector(wx.Dialog):
    def __init__(self, parent, utility):
        self.parent = parent
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        title = self.utility.lang.get('selectbandwidthtitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.bwctrl = BWControl(self)
        sizer.Add(self.bwctrl, 2, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.EXPAND, 5)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('ok'), style = wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('cancel'), style = wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(buttonbox, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizerAndFit(sizer)


    def getUploadBandwidth(self):
        return self.bwctrl.getUploadBandwidth()


class BWControl(wx.Panel):
    
    def __init__(self,parent,*args,**kwargs):
        
        self.utility = parent.utility
        
        wx.Panel.__init__(self, parent, -1, *args, **kwargs)
        
        filebox = wx.BoxSizer(wx.VERTICAL)
        self.uploadbwvals = [ 128/8, 256/8, 512/8, 1024/8, 2048/8, 0]
        self.bwoptions = ['*/128 kbps', '*/256 kbps', '*/512 kbps', '*/1024 kbps', '*/2048 kbps', '*/100 mbps or more']
        self.bwsel = wx.RadioBox(self, 
                                    -1, 
                                    self.utility.lang.get('selectdlulbwprompt'), 
                                    wx.DefaultPosition, 
                                    wx.DefaultSize, 
                                    self.bwoptions, 
                                    3, 
                                    wx.RA_SPECIFY_COLS)

        filebox.Add(self.bwsel, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND, 5)
        filebox.Add(wx.StaticText(self, -1, self.utility.lang.get('selectdlulbwexplan')), 0, wx.ALIGN_CENTER_VERTICAL, 5)
        self.SetSizerAndFit(filebox)

    def getUploadBandwidth(self):
        """ in Kbyte/s """
        index = self.bwsel.GetSelection()
        return self.uploadbwvals[index]
