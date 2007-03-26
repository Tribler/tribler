# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from btn_DetailsHeader import *
from tribler_topButton import *
#[inc]add your include files here

#[inc]end your include

class statusDownloads(wx.Panel):
    def __init__(self,parent,id = -1, pos = wx.Point(0,0), size = wx.Size(300,300), style = wx.TAB_TRAVERSAL, name = "panel"):
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
        self.fileImgBuf=[None] * 4
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/triblerpanel_topright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/statusdownloads_bottom.png",wx.BITMAP_TYPE_PNG)
        self.pn9cImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.pn11cImg0=self.fileImgBuf[2];
        self.pn12cImg0=self.fileImgBuf[3];
        self.pn10cCImg0=self.fileImgBuf[1];
        self.Show(True)
        self.pn9c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.pn9c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9c_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(220,21))
        self.pn10c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st42c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(107,17),wx.ST_NO_AUTORESIZE)
        self.st42c.SetLabel("Downloading (4)")
        self.st42c.SetForegroundColour(wx.Colour(255,255,255))
        self.st42c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn11c = wx.Panel(self,-1,wx.Point(290,0),wx.Size(10,21))
        self.pn11c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11c_VwXEvOnEraseBackground)
        self.pn12c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(298,55))
        self.pn12c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn12c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn12c_VwXEvOnEraseBackground)
        self.st45c = wx.StaticText(self.pn12c,-1,"",wx.Point(8,0),wx.Size(217,265),wx.ST_NO_AUTORESIZE)
        self.st45c.SetLabel("Dit was het nieuws\r\nNos 8 uur Journaal -24 jan. 2007\r\n")
        self.st45c.SetForegroundColour(wx.Colour(0,0,0))
        self.st45c.SetBackgroundColour(wx.Colour(255,255,255))
        self.st46c = wx.StaticText(self.pn12c,-1,"",wx.Point(233,0),wx.Size(42,269),wx.ST_NO_AUTORESIZE)
        self.st46c.SetLabel("70%\r\n33%")
        self.st46c.SetBackgroundColour(wx.Colour(255,255,255))
        self.black_top_left = bgPanel(self, -1, wx.Point(6,274), wx.Size(10,21))
        self.pn10cC = wx.Panel(self,-1,wx.Point(16,274),wx.Size(100,21))
        self.pn10cC.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10cC.SetBackgroundColour(wx.Colour(50,153,204))
        self.pn10cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10cC_VwXEvOnEraseBackground)
        self.black_top_right = bgPanel(self, -1, wx.Point(274,274), wx.Size(10,21))
        self.6_160x90 = bgPanel(self, -1, wx.Point(6,274), wx.Size(302,170))
        self.playbackControls = bgPanel(self, -1, wx.Point(6,274), wx.Size(20,20))
        self.playbackControls.SetBackgroundColour(wx.Colour(0,0,0))
        self.tabs = wx.Panel(self,-1,wx.Point(6,274),wx.Size(20,20))
        self.tabs.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn39cCCC = wx.Panel(self.tabs,-1,wx.Point(3,3),wx.Size(40,15))
        self.pn39cCCC.SetBackgroundColour(wx.Colour(255,255,255))
        self.st60cCC = wx.StaticText(self.pn39cCCC,-1,"",wx.Point(3,3),wx.Size(20,10),wx.ST_NO_AUTORESIZE)
        self.st60cCC.SetLabel("info")
        self.pn39cCC2C = wx.Panel(self.tabs,-1,wx.Point(46,3),wx.Size(65,15))
        self.pn39cCC2C.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCC = wx.StaticText(self.pn39cCC2C,-1,"",wx.Point(3,3),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60cCC.SetLabel("comments")
        self.st60cCC.SetForegroundColour(wx.Colour(0,0,0))
        self.details = wx.Panel(self,-1,wx.Point(6,274),wx.Size(298,348))
        self.details.SetBackgroundColour(wx.Colour(255,255,255))
        self.description = wx.StaticText(self.details,-1,"",wx.Point(3,25),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.description.SetLabel("...")
        self.injectedBy = btn_DetailsHeader(self.details,-1,wxDefaultPosition,wxDefaultSize)
        self.injectedBy.SetDimensions(3,98,20,20)
        self.st202c = wx.StaticText(self.details,-1,"",wx.Point(3,118),wx.Size(114,18),wx.ST_NO_AUTORESIZE)
        self.st202c.SetLabel("injected by")
        self.bm197c = wx.StaticBitmap(self.details,-1,wx.NullBitmap,wx.Point(3,142),wx.Size(55,60))
        self.descriptionC = wx.StaticText(self.details,-1,"",wx.Point(71,139),wx.Size(120,27),wx.ST_NO_AUTORESIZE)
        self.descriptionC.SetLabel("no injector known")
        self.subscribe_20x20 = tribler_topButton(self.details, -1, wx.Point(67,172), wx.Size(20,20))
        self.subscribeText = wx.StaticText(self.details,-1,"",wx.Point(93,172),wx.Size(174,19),wx.ST_NO_AUTORESIZE)
        self.subscribeText.SetLabel("subscribe")
        self.PeopleWho = btn_DetailsHeader(self.details,-1,wxDefaultPosition,wxDefaultSize)
        self.PeopleWho.SetDimensions(3,208,20,20)
        self.st202cC = wx.StaticText(self.details,-1,"",wx.Point(3,228),wx.Size(204,18),wx.ST_NO_AUTORESIZE)
        self.st202cC.SetLabel("People who like this also like")
        self.st188cCC = wx.StaticText(self.details,-1,"",wx.Point(10,249),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.st188cCC.SetLabel("...")
        self.white_bottom = bgPanel(self, -1, wx.Point(6,274), wx.Size(300,5))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz8s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3sC = wx.BoxSizer(wx.VERTICAL)
        self.sz43s = wx.BoxSizer(wx.VERTICAL)
        self.sz44s = wx.BoxSizer(wx.HORIZONTAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.tabsCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz185s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz195s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz186s = wx.BoxSizer(wx.VERTICAL)
        self.sz187s = wx.BoxSizer(wx.VERTICAL)
        self.sz198s = wx.BoxSizer(wx.VERTICAL)
        self.sz200s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz8s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn12c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz3sC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn9c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.SetItemMinSize(self.pn10c,20,10)
        self.sz8s.Add(self.pn11c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3sC.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3sC.Add(self.6_160x90,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3sC.Add(self.playbackControls,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3sC.Add(self.tabs,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz3sC.Add(self.details,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3sC.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz43s.Add(self.st42c,1,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz44s.Add(self.st45c,0,wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,8)
        self.sz44s.Add(self.st46c,0,wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,8)
        self.header.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.header.Add(self.pn10cC,1,wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.pn10cC,20,10)
        self.header.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.tabsCCC.Add(self.pn39cCCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCCC.Add(self.pn39cCC2C,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz61sCC.Add(self.st60cCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sz61sCC.SetItemMinSize(self.st60cCC,20,10)
        self.sz61sCC.Add(self.st60cCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sz184s.Add(self.sz185s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.description,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.sz184s.Add(self.injectedBy,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.st202c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.sz195s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.PeopleWho,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.st202cC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz184s.Add(self.st188cCC,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.sz185s.Add(self.sz186s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz185s.Add(self.sz187s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz195s.Add(self.bm197c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz195s.Add(self.sz198s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz198s.Add(self.descriptionC,0,wx.LEFT|wx.RIGHT|wx.FIXED_MINSIZE,10)
        self.sz198s.Add(self.sz200s,1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz200s.Add(self.subscribe_20x20,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz200s.Add(self.subscribeText,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz43s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pn12c.SetSizer(self.sz44s);self.pn12c.SetAutoLayout(1);self.pn12c.Layout();
        self.tabs.SetSizer(self.tabsCCC);self.tabs.SetAutoLayout(1);self.tabs.Layout();
        self.pn39cCCC.SetSizer(self.sz61sCC);self.pn39cCCC.SetAutoLayout(1);self.pn39cCCC.Layout();
        self.pn39cCC2C.SetSizer(self.sz61sCC);self.pn39cCC2C.SetAutoLayout(1);self.pn39cCC2C.Layout();
        self.details.SetSizer(self.sz184s);self.details.SetAutoLayout(1);self.details.Layout();
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
    def VwXpn9c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn9c,self.pn9cImg0,0)
        self.pn9c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10c,self.pn10cImg0,2)
        self.pn10c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn11c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn11c,self.pn11cImg0,0)
        self.pn11c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn12c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn12c,self.pn12cImg0,0)
        self.pn12c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10cC,self.pn10cCImg0,2)
        self.pn10cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here
    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[6ba]Code event VwX...Don't modify[6ba]#
        #add your code here
        event.Skip()

        return #end function

    def pn12c_VwXEvOnEraseBackground(self,event): #init function
        #[6bd]Code event VwX...Don't modify[6bd]#
        #add your code here
        event.Skip()

        return #end function

    def pn11c_VwXEvOnEraseBackground(self,event): #init function
        #[6bc]Code event VwX...Don't modify[6bc]#
        #add your code here
        event.Skip()

        return #end function

    def pn10cC_VwXEvOnEraseBackground(self,event): #init function
        #[6be]Code event VwX...Don't modify[6be]#
        #add your code here
        event.Skip()

        return #end function

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[6bb]Code event VwX...Don't modify[6bb]#
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
        #[59b]Code VwX...Don't modify[59b]#
        #add your code here

        return #end function

#[win]end your code
