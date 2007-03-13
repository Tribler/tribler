# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from torrentFilter import *
from torrentTabs import *
from torrentGrid import *
#[inc]add your include files here

#[inc]end your include

class torrentOverview(wx.Panel):
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
        self.fileImgBuf=[None] * 7
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/triblerpanel_topright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/triblerpanel_bottomleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[4] = wx.Bitmap("images/triblerpanel_bottomcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[5] = wx.Bitmap("images/add.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[6] = wx.Bitmap("images/triblerpanel_bottomright.png",wx.BITMAP_TYPE_PNG)
        self.triblerPanel_topleftImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.triblerPanel_toprightImg0=self.fileImgBuf[2];
        self.pn9cCImg0=self.fileImgBuf[3];
        self.pn10cCImg0=self.fileImgBuf[4];
        self.bm159cImg0=self.fileImgBuf[5];
        self.pn11cCImg0=self.fileImgBuf[6];
        self.Show(True)
        self.triblerPanel_topleft = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.triblerPanel_topleft.SetBackgroundColour(wx.Colour(0,0,0))
        self.triblerPanel_topleft.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtriblerPanel_topleft_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(20,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(194,17),wx.ST_NO_AUTORESIZE)
        self.st64c.SetLabel("Content")
        self.st64c.SetForegroundColour(wx.Colour(255,255,255))
        self.triblerPanel_topright = wx.Panel(self,-1,wx.Point(613,0),wx.Size(10,21))
        self.triblerPanel_topright.SetBackgroundColour(wx.Colour(0,0,0))
        self.triblerPanel_topright.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtriblerPanel_topright_VwXEvOnEraseBackground)
        self.torrentFilter = torrentFilter(self,-1,wxDefaultPosition,wxDefaultSize)
        self.torrentFilter.SetDimensions(0,21,448,20)
        self.torrentTabs = torrentTabs(self,-1,wxDefaultPosition,wxDefaultSize)
        self.torrentTabs.SetDimensions(0,41,20,20)
        self.pn9cC = wx.Panel(self,-1,wx.Point(0,403),wx.Size(10,28))
        self.pn9cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9cC_VwXEvOnEraseBackground)
        self.pn10cC = wx.Panel(self,-1,wx.Point(10,399),wx.Size(20,28))
        self.pn10cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn10cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10cC_VwXEvOnEraseBackground)
        self.bm159c = wx.StaticBitmap(self.pn10cC,-1,self.bm159cImg0,wx.Point(3,3),wx.Size(16,16))
        self.bm159c.SetBackgroundColour(wx.Colour(255,255,255))
        self.st158c = wx.StaticText(self.pn10cC,-1,"",wx.Point(1,1),wx.Size(279,14),wx.ST_NO_AUTORESIZE)
        self.st158c.SetLabel("add friend")
        self.st158c.SetForegroundColour(wx.Colour(0,0,0))
        self.st158c.SetBackgroundColour(wx.Colour(255,255,255))
        self.pn11cC = wx.Panel(self,-1,wx.Point(433,400),wx.Size(190,28))
        self.pn11cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11cC_VwXEvOnEraseBackground)
        self.torrentGrid = torrentGrid(self,-1,wxDefaultPosition,wxDefaultSize)
        self.torrentGrid.SetDimensions(3,64,617,235)
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz157s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.torrentFilter,0,wx.ALIGN_LEFT|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.torrentTabs,0,wx.ALIGN_LEFT|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.torrentGrid,1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.footer,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.triblerPanel_topleft,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.pn10c,20,10)
        self.header.Add(self.triblerPanel_topright,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.pn9cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.pn10cC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.SetItemMinSize(self.pn10cC,20,10)
        self.footer.Add(self.pn11cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz157s.Add(self.bm159c,0,wx.FIXED_MINSIZE,3)
        self.sz157s.Add(self.st158c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,1)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pn10cC.SetSizer(self.sz157s);self.pn10cC.SetAutoLayout(1);self.pn10cC.Layout();
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
    def VwXtriblerPanel_topleft_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.triblerPanel_topleft,self.triblerPanel_topleftImg0,0)
        self.triblerPanel_topleft_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10c,self.pn10cImg0,2)
        self.pn10c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtriblerPanel_topright_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.triblerPanel_topright,self.triblerPanel_toprightImg0,0)
        self.triblerPanel_topright_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn9cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn9cC,self.pn9cCImg0,0)
        self.pn9cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10cC,self.pn10cCImg0,2)
        self.pn10cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn11cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn11cC,self.pn11cCImg0,0)
        self.pn11cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def bla(self):
        pass
        
    def pn9cC_VwXEvOnEraseBackground(self,event): #init function
        #[325]Code event VwX...Don't modify[325]#
        #add your code here
        event.Skip()

        return #end function

    def pn11cC_VwXEvOnEraseBackground(self,event): #init function
        #[327]Code event VwX...Don't modify[327]#
        #add your code here
        event.Skip()

        return #end function

    def pn10cC_VwXEvOnEraseBackground(self,event): #init function
        #[326]Code event VwX...Don't modify[326]#
        #add your code here
        event.Skip()

        return #end function


    def triblerPanel_topleft_VwXEvOnEraseBackground(self,event): #init function
        #[6f2]Code event VwX...Don't modify[6f2]#
        #add your code here
        event.Skip()

        return #end function


    def triblerPanel_topright_VwXEvOnEraseBackground(self,event): #init function
        #[ c1]Code event VwX...Don't modify[ c1]#
        #add your code here
        event.Skip()

        return #end function

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[ c0]Code event VwX...Don't modify[ c0]#
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
        #[ bf]Code VwX...Don't modify[ bf]#
        #add your code here

        return #end function

#[win]end your code
