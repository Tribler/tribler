#########################################################################
# Author : Tim Tucker
# Description : Ask whether or not to overwrite files
#########################################################################
import wx
from os import path

#
# Will return one several values:
#
# -2: No to All
# -1: No
#  1: Yes
#  2: Yes to All
#
class DupFileDialog(wx.Dialog):
    def __init__(self, torrent, filename, single = True):
        self.utility = torrent.utility
        
        title = self.utility.lang.get('extracterrorduplicate')
        
        pre = wx.PreDialog()
        pre.Create(None, -1, title)
        self.this = pre.this

        message = "Torrent : "+ torrent.filename + "\n" + \
                  "File : " + filename + "\n" +\
                  self.utility.lang.get('extracterrorduplicatemsg')

        outerbox = wx.BoxSizer( wx.VERTICAL )

        outerbox.Add(wx.StaticText(self, -1, message), 0, wx.ALIGN_LEFT|wx.ALL, 5)
               
        self.yesbtn = wx.Button(self, -1, self.utility.lang.get('yes'))
        self.Bind(wx.EVT_BUTTON, self.onYES, self.yesbtn)

        self.yestoallbtn = wx.Button(self, -1, self.utility.lang.get('yestoall'))
        self.Bind(wx.EVT_BUTTON, self.onYESTOALL, self.yestoallbtn)
        
        self.nobtn = wx.Button(self, -1, self.utility.lang.get('no'))
        self.Bind(wx.EVT_BUTTON, self.onNO, self.nobtn)

        self.notoallbtn = wx.Button(self, -1, self.utility.lang.get('notoall'))
        self.Bind(wx.EVT_BUTTON, self.onNOTOALL, self.notoallbtn)

        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(self.yesbtn, 0, wx.ALL, 5)
        buttonbox.Add(self.yestoallbtn, 0, wx.ALL, 5)
        buttonbox.Add(self.nobtn, 0, wx.ALL, 5)
        buttonbox.Add(self.notoallbtn, 0, wx.ALL, 5)

        outerbox.Add( buttonbox, 0, wx.ALIGN_CENTER)

        self.SetAutoLayout( True )
        self.SetSizer( outerbox )
        self.Fit()
        
    def onYES(self, event):
        self.EndModal(1)

    def onYESTOALL(self, event):
        self.EndModal(2)

    def onNO(self, event):
        self.EndModal(-1)
        
    def onNOTOALL(self, event):
        self.EndModal(-2)