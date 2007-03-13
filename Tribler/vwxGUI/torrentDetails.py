# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class torrentDetails(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,462),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf=[None] * 10
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/triblerpanel_topright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/triblerpanel_bottomleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[4] = wx.Bitmap("images/triblerpanel_bottomcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[5] = wx.Bitmap("images/triblerpanel_bottomright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[6] = wx.Bitmap("images/6_160x90.jpg",wx.BITMAP_TYPE_JPEG)
        self.fileImgBuf[7] = wx.Bitmap("images/size.gif",wx.BITMAP_TYPE_GIF)
        self.fileImgBuf[8] = wx.Bitmap("images/up.gif",wx.BITMAP_TYPE_GIF)
        self.fileImgBuf[9] = wx.Bitmap("images/down.gif",wx.BITMAP_TYPE_GIF)
        self.pn9cImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.pn11cImg0=self.fileImgBuf[2];
        self.pn9cCImg0=self.fileImgBuf[3];
        self.pn10cCImg0=self.fileImgBuf[4];
        self.pn11cCImg0=self.fileImgBuf[5];
        self.pn15cCImg0=self.fileImgBuf[6];
        self.bm18cCImg0=self.fileImgBuf[7];
        self.bm18cImg0=self.fileImgBuf[8];
        self.bm19cImg0=self.fileImgBuf[9];
        self.Show(True)
        self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.pn9c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.pn9c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9c_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(218,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(3,3),wx.Size(194,17),wx.ST_NO_AUTORESIZE)
        self.st64c.SetLabel("The sony bravia commercial")
        self.pn11c = wx.Panel(self,-1,wx.Point(108,0),wx.Size(10,21))
        self.pn11c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11c_VwXEvOnEraseBackground)
        self.pn9cC = wx.Panel(self,-1,wx.Point(0,455),wx.Size(10,28))
        self.pn9cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9cC_VwXEvOnEraseBackground)
        self.pn10cC = wx.Panel(self,-1,wx.Point(10,455),wx.Size(155,28))
        self.pn10cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn10cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10cC_VwXEvOnEraseBackground)
        self.pn11cC = wx.Panel(self,-1,wx.Point(108,432),wx.Size(190,28))
        self.pn11cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11cC_VwXEvOnEraseBackground)
        self.pn12c = wx.Panel(self,-1,wx.Point(0,25),wx.Size(298,430))
        self.pn12c.SetBackgroundColour(wx.Colour(255,255,255))
        self.pn48c = wx.Panel(self.pn12c,-1,wx.Point(0,0),wx.Size(290,100))
        self.pn48c.SetBackgroundColour(wx.Colour(219,219,219))
        self.pn15cC = wx.Panel(self.pn48c,-1,wx.Point(6,6),wx.Size(160,90),wx.SIMPLE_BORDER)
        self.pn15cC.SetBackgroundColour(wx.Colour(219,219,219))
        self.pn15cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn15cC_VwXEvOnEraseBackground)
        self.st5cCCaa = wx.StaticText(self.pn48c,-1,"",wx.Point(175,3),wx.Size(117,13),wx.ST_NO_AUTORESIZE)
        self.st5cCCaa.SetLabel("> download")
        self.st5cCCaa.SetForegroundColour(wx.Colour(255,85,0))
        self.pn44c = wx.Panel(self.pn12c,-1,wx.Point(0,100),wx.Size(20,20))
        self.pn44c.SetBackgroundColour(wx.Colour(110,110,110))
        self.pn39cCC = wx.Panel(self.pn44c,-1,wx.Point(3,3),wx.Size(40,15))
        self.pn39cCC.SetBackgroundColour(wx.Colour(255,255,255))
        self.st60c = wx.StaticText(self.pn39cCC,-1,"",wx.Point(5,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60c.SetLabel("info")
        self.pn39cCC2 = wx.Panel(self.pn44c,-1,wx.Point(46,3),wx.Size(65,15))
        self.pn39cCC2.SetBackgroundColour(wx.Colour(205,205,205))
        self.bm18cC = wx.StaticBitmap(self.pn48c,-1,self.bm18cCImg0,wx.Point(178,-185),wx.Size(11,16))
        self.st5cCC = wx.StaticText(self.pn48c,-1,"",wx.Point(192,67),wx.Size(18,11),wx.ST_NO_AUTORESIZE)
        self.st5cCC.SetLabel("avi")
        self.st5cCC.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCfdsf = wx.StaticText(self.pn48c,-1,"",wx.Point(210,67),wx.Size(8,16),wx.ST_NO_AUTORESIZE)
        self.st5cCfdsf.SetLabel("| ")
        self.st5cCfdsf.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCCCC = wx.StaticText(self.pn48c,-1,"",wx.Point(218,67),wx.Size(35,11))
        self.st5cCCCC.SetLabel("130 MB")
        self.st5cCCCC.SetFont(wx.Font(8,74,90,90,0,"Tahoma"))
        self.st5cCCCC.SetForegroundColour(wx.Colour(128,128,128))
        self.bm18c = wx.StaticBitmap(self.pn48c,-1,self.bm18cImg0,wx.Point(178,-185),wx.Size(5,8))
        self.st20c = wx.StaticText(self.pn48c,-1,"",wx.Point(189,82),wx.Size(19,15),wx.ST_NO_AUTORESIZE)
        self.st20c.SetLabel("40")
        self.st20c.SetForegroundColour(wx.Colour(128,128,128))
        self.bm19c = wx.StaticBitmap(self.pn48c,-1,self.bm19cImg0,wx.Point(214,-185),wx.Size(5,8))
        self.st21c = wx.StaticText(self.pn48c,-1,"",wx.Point(225,74),wx.Size(19,15),wx.ST_NO_AUTORESIZE)
        self.st21c.SetLabel("10")
        self.st21c.SetForegroundColour(wx.Colour(128,128,128))
        self.st60cC = wx.StaticText(self.pn39cCC2,-1,"",wx.Point(5,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60cC.SetLabel("comments")
        self.st60cC.SetForegroundColour(wx.Colour(0,0,0))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz8s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz8sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz13s = wx.BoxSizer(wx.VERTICAL)
        self.sz14sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz16sC = wx.BoxSizer(wx.VERTICAL)
        self.sz24sC = wx.BoxSizer(wx.VERTICAL)
        self.tabsCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz22s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz17s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz8s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn12c,1,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz3s.Add(self.sz8sC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn9c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.SetItemMinSize(self.pn10c,20,10)
        self.sz8s.Add(self.pn11c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn9cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn10cC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.SetItemMinSize(self.pn10cC,20,10)
        self.sz8sC.Add(self.pn11cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz13s.Add(self.pn48c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz13s.Add(self.pn44c,0,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz14sCC.Add(self.pn15cC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz14sCC.Add(self.sz16sC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz16sC.Add(self.sz24sC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz16sC.Add(self.sz22s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz16sC.Add(self.sz17s,0,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz24sC.Add(self.st5cCCaa,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC2,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz61s.Add(self.st60c,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sz22s.Add(self.bm18cC,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cCfdsf,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cCCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.bm18c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.st20c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.bm19c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.st21c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz61sC.Add(self.st60cC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pn12c.SetSizer(self.sz13s);self.pn12c.SetAutoLayout(1);self.pn12c.Layout();
        self.pn48c.SetSizer(self.sz14sCC);self.pn48c.SetAutoLayout(1);self.pn48c.Layout();
        self.pn44c.SetSizer(self.tabsCC);self.pn44c.SetAutoLayout(1);self.pn44c.Layout();
        self.pn39cCC.SetSizer(self.sz61s);self.pn39cCC.SetAutoLayout(1);self.pn39cCC.Layout();
        self.pn39cCC2.SetSizer(self.sz61sC);self.pn39cCC2.SetAutoLayout(1);self.pn39cCC2.Layout();
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
    def VwXpn15cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn15cC,self.pn15cCImg0,0)
        self.pn15cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def pn9cC_VwXEvOnEraseBackground(self,event): #init function
        #[146]Code event VwX...Don't modify[146]#
        #add your code here
        event.Skip()

        return #end function

    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[143]Code event VwX...Don't modify[143]#
        #add your code here
        event.Skip()

        return #end function

    def pn15cC_VwXEvOnEraseBackground(self,event): #init function
        #[149]Code event VwX...Don't modify[149]#
        #add your code here
        event.Skip()

        return #end function

    def pn11cC_VwXEvOnEraseBackground(self,event): #init function
        #[148]Code event VwX...Don't modify[148]#
        #add your code here
        event.Skip()

        return #end function

    def pn11c_VwXEvOnEraseBackground(self,event): #init function
        #[145]Code event VwX...Don't modify[145]#
        #add your code here
        event.Skip()

        return #end function

    def pn10cC_VwXEvOnEraseBackground(self,event): #init function
        #[147]Code event VwX...Don't modify[147]#
        #add your code here
        event.Skip()

        return #end function

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[144]Code event VwX...Don't modify[144]#
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
        #[142]Code VwX...Don't modify[142]#
        #add your code here

        return #end function

#[win]end your code
