# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from tribler_topButton import *
#[inc]add your include files here

#[inc]end your include

class personsTab_advanced(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,350),style = wx.TAB_TRAVERSAL,name = 'panel'):
        pre=wx.PrePanel()
        self.OnPreCreate()
        pre.Create(parent,id,pos,size,style,name)
        self.PostCreate(pre)
        self.initBefore()
        self.VwXinit()
        self.initAfter()

    def __del__(self):
        self.Ddel()
        return


    def VwXinit(self):
        self.Show(True)
        self.st209cCC = wx.StaticText(self,-1,"",wx.Point(8,7),wx.Size(150,18),wx.ST_NO_AUTORESIZE)
        self.st209cCC.SetLabel("last info exchange:\r\ntotal number of exchanges:")
        self.lastExchangeField = wx.StaticText(self,-1,"",wx.Point(158,7),wx.Size(60,18),wx.ST_NO_AUTORESIZE)
        self.lastExchangeField.SetLabel("unknown")
        self.st209c = wx.StaticText(self,-1,"",wx.Point(8,25),wx.Size(150,18),wx.ST_NO_AUTORESIZE)
        self.st209c.SetLabel("total number of exchanges:")
        self.noExchangeField = wx.StaticText(self,-1,"",wx.Point(158,25),wx.Size(60,18))
        self.noExchangeField.SetLabel("unknown")
        self.st209cC = wx.StaticText(self,-1,"",wx.Point(8,43),wx.Size(150,18),wx.ST_NO_AUTORESIZE)
        self.st209cC.SetLabel("number of times connected:")
        self.timesConnectedField = wx.StaticText(self,-1,"",wx.Point(158,43),wx.Size(60,18))
        self.timesConnectedField.SetLabel("unknown")
        self.addAsFriend = tribler_topButton(self, -1, wx.Point(272,6), wx.Size(55,55))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz237s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz238s = wx.BoxSizer(wx.VERTICAL)
        self.lastExchangeSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.noExchangeSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.timesConnectedSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz237s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add([292,278],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz237s.Add(self.vert_sz238s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz237s.Add(self.downloadSizer,1,wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.vert_sz238s.Add(self.lastExchangeSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238s.Add(self.noExchangeSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238s.Add(self.timesConnectedSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.lastExchangeSizer.Add(self.st209cCC,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.lastExchangeSizer.Add(self.lastExchangeField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.noExchangeSizer.Add(self.st209c,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.noExchangeSizer.Add(self.noExchangeField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.timesConnectedSizer.Add(self.st209cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.timesConnectedSizer.Add(self.timesConnectedField,0,wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.downloadSizer.Add([13,52],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add(self.addAsFriend,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        return
    def VwXDelComp(self):
        return

#[win]add your code here

    def OnPreCreate(self):
        #add your code here

        return

    def initBefore(self):
        #add your code here

        return

    def initAfter(self):
        #add your code here

        return

    def Ddel(self): #init function
        #[1c2]Code VwX...Don't modify[1c2]#
        #add your code here

        return #end function

#[win]end your code
