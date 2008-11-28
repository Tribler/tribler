# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import ImagePanel
from filesGrid import *
from standardPager import *
#[inc]add your include files here

#[inc]end your include

class filesOverview(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(677,485),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.infoIconC = ImagePanel(self,-1,wxDefaultPosition,wxDefaultSize)
        self.infoIconC.SetDimensions(6,475,8,8)
        self.infoIconC.SetToolTipString('Files received from other Tribler users, thus showing what is available in the Tribler network \\n(automatic process)')
        self.filesGrid = filesGrid(self,-1,wxDefaultPosition,wxDefaultSize)
        self.filesGrid.SetDimensions(0,1,675,309)
        self.standardPager = standardPager(self,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(370,446,297,23)
        self.vertical = wx.BoxSizer(wx.VERTICAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.vertical.Add([675,1],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical.Add(self.filesGrid,1,wx.EXPAND|wx.FIXED_MINSIZE,103)
        self.vertical.Add(self.footer,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical.Add(self.infoIconC,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.FIXED_MINSIZE,6)
        self.footer.Add([370,28],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.standardPager,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.footer.Add([8,28],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.SetSizer(self.vertical);self.SetAutoLayout(1);self.Layout();
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
        #[6a7]Code VwX...Don't modify[6a7]#
        #add your code here

        return #end function

#[win]end your code
