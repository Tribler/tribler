# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
#[inc]add your include files here

#[inc]end your include

class statusDownloads(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,155),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf=[None] * 1
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.pn10cImg0=self.fileImgBuf[0];
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.black_top_left = bgPanel(self, -1, wx.Point(0,0), wx.Size(10,20))
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(100,20))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st28c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,3),wx.Size(114,15),wx.ST_NO_AUTORESIZE)
        self.st28c.SetLabel("Downloading ...")
        self.st28c.SetBackgroundColour(wx.Colour(0,0,0))
        self.st30c = wx.StaticText(self.pn10c,-1,"",wx.Point(114,3),wx.Size(134,15),wx.ST_NO_AUTORESIZE)
        self.st30c.SetLabel("down: 30 KB/s | up: 20 KB/s")
        self.st30c.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(288,0), wx.Size(10,20))
        self.pn34c = wx.Panel(self,-1,wx.Point(0,30),wx.Size(298,70))
        self.pn34c.SetBackgroundColour(wx.Colour(255,255,255))
        self.st32c = wx.StaticText(self.pn34c,-1,"",wx.Point(1,1),wx.Size(292,53),wx.ST_NO_AUTORESIZE)
        self.st32c.SetLabel("download text etc.\r\n")
        self.white_bottom = bgPanel(self, -1, wx.Point(3,118), wx.Size(300,5))
        self.sz23s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.sz29s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz23s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz23s.Add(self.pn34c,1,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.sz23s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.black_top_left,0,wx.FIXED_MINSIZE,0)
        self.header.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.pn10c,20,10)
        self.header.Add(self.black_top_right,0,wx.FIXED_MINSIZE,0)
        self.sz29s.Add(self.st28c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz29s.Add(self.st30c,0,wx.TOP|wx.EXPAND|wx.ALIGN_RIGHT|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz23s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz29s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.Refresh()
        return
    def VwXDrawBackImg(self,event,win,bitMap,opz):
        if (event.GetDC()):
            dc=event.GetDC()
        else: dc = wx.ClientDC(win)
        dc.SetBackground(wx.Brush(win.GetBackgroundColour(),wx.SOLID))
        dc.Clear()
        if (opz==0):
            dc.DrawBitmap(bitMap,0, 0, 0)
        if (opz==1):
            rec=wx.Rect()
            rec=win.GetClientRect()
            rec.SetLeft((rec.GetWidth()-bitMap.GetWidth())   / 2)
            rec.SetTop ((rec.GetHeight()-bitMap.GetHeight()) / 2)
            dc.DrawBitmap(bitMap,rec.GetLeft(),rec.GetTop(),0)
        if (opz==2):
            rec=wx.Rect()
            rec=win.GetClientRect()
            for y in range(0,rec.GetHeight(),bitMap.GetHeight()):
                for x in range(0,rec.GetWidth(),bitMap.GetWidth()):
                    dc.DrawBitmap(bitMap,x,y,0)

    def VwXDelComp(self):
        return
    def VwXpn10c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10c,self.pn10cImg0,2)
        self.pn10c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[3dd]Code event VwX...Don't modify[3dd]#
        #add your code here
        event.Skip()

        return #end function

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
        #[3dc]Code VwX...Don't modify[3dc]#
        #add your code here

        return #end function

#[win]end your code
