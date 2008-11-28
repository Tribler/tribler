# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from libraryGrid import *
from bgPanel import ImagePanel
from standardPager import *
#[inc]add your include files here

#[inc]end your include

class libraryOverview(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(625,430),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.libraryGrid = libraryGrid(self,-1,wxDefaultPosition,wxDefaultSize)
        self.libraryGrid.SetDimensions(0,0,20,20)
        self.infoIcon = [None] * 3
        self.infoIcon[1] = ImagePanel(self,-1,wxDefaultPosition,wxDefaultSize)
        self.infoIcon[1].SetDimensions(0,420,8,8)
        self.infoIcon[1].index=1
        self.infoIcon[1].SetToolTipString('In progress and finished downloads')
        self.infoIcon[1].Show(False)
        self.standardPager = standardPager(self,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(307,391,307,23)
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add([623,0],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.libraryGrid,1,wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sz3s.Add(self.footer,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.infoIcon[1],0,wx.TOP|wx.RIGHT|wx.FIXED_MINSIZE,6)
        self.footer.Add([307,28],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.standardPager,1,wx.TOP,5)
        self.footer.Add([8,28],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
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
        #[2ae]Code VwX...Don't modify[2ae]#
        #add your code here

        return #end function

#[win]end your code
