#########################################################################
# Author : Tim Tucker
# Description : Ask whether or not to associate ABC with torrents
#########################################################################
import wx
from os import path

class RegCheckDialog(wx.Dialog):
    def __init__(self, parent):
        self.utility = parent.utility
        
        title = self.utility.lang.get('associate')
        
        pre = wx.PreDialog()
        pre.Create(parent, -1, title)
        self.this = pre.this

        outerbox = wx.BoxSizer( wx.VERTICAL )

        outerbox.Add(wx.StaticText(self, -1,  self.utility.lang.get('notassociated')), 0, wx.ALIGN_LEFT|wx.ALL, 5)
               
        self.yesbtn = wx.Button(self, -1, self.utility.lang.get('yes'))
        self.Bind(wx.EVT_BUTTON, self.onYES, self.yesbtn)
        
        self.nobtn = wx.Button(self, -1, self.utility.lang.get('no'))
        self.Bind(wx.EVT_BUTTON, self.onNO, self.nobtn)
        
        self.cancelbtn = wx.Button(self, wx.ID_CANCEL, self.utility.lang.get('cancel'))

        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(self.yesbtn, 0, wx.ALL, 5)
        buttonbox.Add(self.nobtn, 0, wx.ALL, 5)
        buttonbox.Add(self.cancelbtn, 0, wx.ALL, 5)

        outerbox.Add( buttonbox, 0, wx.ALIGN_CENTER)

        self.SetAutoLayout( True )
        self.SetSizer( outerbox )
        self.Fit()
        
    def onYES(self, event):
        self.apply(True)
        self.EndModal(wx.ID_YES)
        
    def onNO(self, event):
        self.apply(False)
        self.EndModal(wx.ID_NO)
        
    def apply(self, register):
        self.utility.regchecker.updateRegistry(register)
        
        self.utility.config.Write('associate', register, "boolean")
        self.utility.config.Flush()
