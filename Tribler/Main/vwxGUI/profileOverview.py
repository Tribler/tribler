# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from tribler_topButton import *
from bgPanel import ImagePanel
#[inc]add your include files here

#[inc]end your include

class profileOverview(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(625,510),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.SetBackgroundColour(wx.Colour(102,102,102))
        self.thumb = bgPanel(self, -1, wx.Point(15,0), wx.Size(80,80))
        self.st227c = wx.StaticText(self,-1,"",wx.Point(110,66),wx.Size(89,23),wx.ST_NO_AUTORESIZE)
        self.st227c.SetLabel("nickname:")
        self.st227c.SetFont(wx.Font(9,74,90,90,0,"Verdana"))
        self.edit = tribler_topButton(self, -1, wx.Point(110,128), wx.Size(37,16))
        self.myNameField = wx.StaticText(self,-1,"",wx.Point(201,66),wx.Size(99,18),wx.ST_NO_AUTORESIZE)
        self.myNameField.SetLabel("_")
        self.myNameField.SetFont(wx.Font(9,74,90,92,0,"Verdana"))
        self.infoIconC = ImagePanel(self,-1,wxDefaultPosition,wxDefaultSize)
        self.infoIconC.SetDimensions(3,117,8,8)
        self.infoIconC.SetToolTipString('Your profile; your name and Tribler icon are visible to other Tribler users.')
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.profile = wx.BoxSizer(wx.HORIZONTAL)
        self.sz223s = wx.BoxSizer(wx.VERTICAL)
        self.sz226s = wx.BoxSizer(wx.VERTICAL)
        self.vsizer1 = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.hsizer,0,wx.EXPAND|wx.FIXED_MINSIZE,13)
        self.sz3s.Add(self.infoIconC,0,wx.TOP|wx.RIGHT|wx.FIXED_MINSIZE,6)
        self.hsizer.Add(self.vsizer1,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.profile.Add(self.thumb,0,wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.profile.Add(self.sz223s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.profile.Add(self.sz226s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz223s.Add(self.st227c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz223s.Add([89,39],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz223s.Add(self.edit,0,wx.FIXED_MINSIZE,3)
        self.sz226s.Add(self.myNameField,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.vsizer1.Add(self.profile,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
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
        #[64c]Code VwX...Don't modify[64c]#
        #add your code here

        return #end function

#[win]end your code
