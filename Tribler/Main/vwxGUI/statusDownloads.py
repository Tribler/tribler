# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
#[inc]add your include files here

#[inc]end your include

class statusDownloads(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(260,425),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.statusHeaderImg0=self.fileImgBuf[0];
        self.Show(True)
        self.statusHeader = wx.Panel(self,-1,wx.Point(0,237),wx.Size(238,20))
        self.statusHeader.SetForegroundColour(wx.Colour(255,255,255))
        self.statusHeader.SetBackgroundColour(wx.Colour(0,0,0))
        self.statusHeader.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXstatusHeader_VwXEvOnEraseBackground)
        self.Downloading = wx.StaticText(self.statusHeader,-1,"",wx.Point(3,3),wx.Size(89,15),wx.ST_NO_AUTORESIZE)
        self.Downloading.Show(False)
        self.Downloading.SetLabel("---")
        self.Downloading.SetForegroundColour(wx.Colour(255,255,255))
        self.Downloading.SetBackgroundColour(wx.Colour(0,0,0))
        self.downSpeed = wx.StaticText(self.statusHeader,-1,"",wx.Point(20,3),wx.Size(69,15),wx.ST_NO_AUTORESIZE)
        self.downSpeed.SetLabel("0 KB/s")
        self.downSpeed.SetForegroundColour(wx.Colour(255,255,255))
        self.downSpeed.SetBackgroundColour(wx.Colour(0,0,0))
        self.download1 = wx.StaticText(self,-1,"",wx.Point(3,32),wx.Size(170,18),wx.ST_NO_AUTORESIZE)
        self.download1.SetLabel("\r\n")
        self.download1.SetForegroundColour(wx.Colour(0,0,0))
        self.percent1 = wx.StaticText(self,-1,"",wx.Point(246,23),wx.Size(42,18),wx.ST_NO_AUTORESIZE)
        self.percent1.SetForegroundColour(wx.Colour(0,0,0))
        self.download2 = wx.StaticText(self,-1,"",wx.Point(3,41),wx.Size(170,18),wx.ST_NO_AUTORESIZE)
        self.download2.SetForegroundColour(wx.Colour(0,0,0))
        self.percent2 = wx.StaticText(self,-1,"",wx.Point(246,41),wx.Size(42,18),wx.ST_NO_AUTORESIZE)
        self.percent2.SetForegroundColour(wx.Colour(0,0,0))
        self.download3 = wx.StaticText(self,-1,"",wx.Point(10,59),wx.Size(170,18),wx.ST_NO_AUTORESIZE)
        self.download3.SetForegroundColour(wx.Colour(0,0,0))
        self.percent3 = wx.StaticText(self,-1,"",wx.Point(246,59),wx.Size(42,18),wx.ST_NO_AUTORESIZE)
        self.percent3.SetForegroundColour(wx.Colour(0,0,0))
        self.download4 = wx.StaticText(self,-1,"",wx.Point(10,77),wx.Size(170,18),wx.ST_NO_AUTORESIZE)
        self.download4.SetForegroundColour(wx.Colour(0,0,0))
        self.percent4 = wx.StaticText(self,-1,"",wx.Point(246,77),wx.Size(42,18),wx.ST_NO_AUTORESIZE)
        self.percent4.SetForegroundColour(wx.Colour(0,0,0))
        self.down_White = bgPanel(self.statusHeader, -1, wx.Point(116,2), wx.Size(16,16))
        self.up_White = bgPanel(self.statusHeader, -1, wx.Point(277,3), wx.Size(16,16))
        self.upSpeed = wx.StaticText(self.statusHeader,-1,"",wx.Point(201,3),wx.Size(94,15),wx.ST_NO_AUTORESIZE)
        self.upSpeed.SetLabel("0 KB/s")
        self.upSpeed.SetForegroundColour(wx.Colour(255,255,255))
        self.upSpeed.SetBackgroundColour(wx.Colour(0,0,0))
        self.playList = wx.Panel(self,-1,wx.Point(3,3),wx.Size(246,55))
        self.sz23s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer4 = wx.BoxSizer(wx.HORIZONTAL)
        self.sz57s = wx.BoxSizer(wx.VERTICAL)
        self.sz29s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz23s.Add(self.sz57s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz23s.Add(self.header,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz23s.Add(self.sizer1,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz23s.Add(self.sizer2,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz23s.Add(self.sizer3,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz23s.Add(self.sizer4,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.statusHeader,1,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.header.SetItemMinSize(self.statusHeader,20,10)
        self.sizer1.Add(self.download1,1,wx.TOP|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sizer1.Add(self.percent1,0,wx.TOP|wx.FIXED_MINSIZE,3)
        self.sizer2.Add(self.download2,1,wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sizer2.Add(self.percent2,0,wx.FIXED_MINSIZE,10)
        self.sizer3.Add(self.download3,1,wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sizer3.Add(self.percent3,0,wx.FIXED_MINSIZE,10)
        self.sizer4.Add(self.download4,1,wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sizer4.Add(self.percent4,0,wx.FIXED_MINSIZE,10)
        self.sz57s.Add(self.playList,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz29s.Add(self.Downloading,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz29s.Add(self.down_White,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz29s.Add(self.downSpeed,0,wx.TOP|wx.EXPAND|wx.ALIGN_RIGHT|wx.FIXED_MINSIZE,3)
        self.sz29s.Add(self.up_White,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz29s.Add(self.upSpeed,0,wx.TOP|wx.EXPAND|wx.ALIGN_RIGHT|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz23s);self.SetAutoLayout(1);self.Layout();
        self.statusHeader.SetSizer(self.sz29s);self.statusHeader.SetAutoLayout(1);self.statusHeader.Layout();
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
    def VwXstatusHeader_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.statusHeader,self.statusHeaderImg0,2)
        self.statusHeader_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def statusHeader_VwXEvOnEraseBackground(self,event): #init function
        #[51b]Code event VwX...Don't modify[51b]#
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
        #[51a]Code VwX...Don't modify[51a]#
        #add your code here

        return #end function

#[win]end your code
