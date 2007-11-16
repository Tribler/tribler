# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class triblerPanel_Overview(wx.Panel):
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
        self.pn9cImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.pn11cImg0=self.fileImgBuf[2];
        self.pn9cCImg0=self.fileImgBuf[3];
        self.pn10cCImg0=self.fileImgBuf[4];
        self.bm159cImg0=self.fileImgBuf[5];
        self.pn11cCImg0=self.fileImgBuf[6];
        self.Show(True)
        self.pn9c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.pn9c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9c_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(20,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(194,17),wx.ST_NO_AUTORESIZE)
        self.st64c.SetLabel("Content")
        self.st64c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn11c = wx.Panel(self,-1,wx.Point(613,0),wx.Size(10,21))
        self.pn11c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11c_VwXEvOnEraseBackground)
        self.pn48c = wx.Panel(self,-1,wx.Point(1,21),wx.Size(621,100))
        self.pn48c.SetBackgroundColour(wx.Colour(219,219,219))
        self.st160c = wx.StaticText(self.pn48c,-1,"",wx.Point(8,40),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st160c.SetLabel("  audio")
        self.tx171c = wx.TextCtrl(self.pn48c,-1,"",wx.Point(8,8),wx.Size(135,18))
        self.bt172c = wx.Button(self.pn48c,-1,"",wx.Point(198,8),wx.Size(20,18))
        self.bt172c.SetLabel("search")
        self.pn44c = wx.Panel(self,-1,wx.Point(1,121),wx.Size(20,20))
        self.pn44c.SetBackgroundColour(wx.Colour(110,110,110))
        self.pn39cCC = wx.Panel(self.pn44c,-1,wx.Point(3,3),wx.Size(40,15))
        self.pn39cCC.SetBackgroundColour(wx.Colour(255,255,255))
        self.st60c = wx.StaticText(self.pn39cCC,-1,"",wx.Point(4,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60c.SetLabel("all")
        self.pn39cCC2C = wx.Panel(self.pn44c,-1,wx.Point(46,3),wx.Size(45,15))
        self.pn39cCC2C.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCC = wx.StaticText(self.pn39cCC2C,-1,"",wx.Point(4,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60cCC.SetLabel("video")
        self.st60cCC.SetForegroundColour(wx.Colour(0,0,0))
        self.tab = wx.Panel(self.pn44c,-1,wx.Point(211,3),wx.Size(65,15))
        self.tab.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCCCC = wx.StaticText(self.tab,-1,"",wx.Point(4,0),wx.Size(84,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCCCC.SetLabel("videoclips")
        self.st60cCCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.pn39cCC2CC = wx.Panel(self.pn44c,-1,wx.Point(94,3),wx.Size(50,15))
        self.pn39cCC2CC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCC = wx.StaticText(self.pn39cCC2CC,-1,"",wx.Point(-1,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCC.SetLabel("audio")
        self.st60cCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.pn39cCC2CCC = wx.Panel(self.pn44c,-1,wx.Point(147,3),wx.Size(55,15))
        self.pn39cCC2CCC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCCC = wx.StaticText(self.pn39cCC2CCC,-1,"",wx.Point(4,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCCC.SetLabel("pictures")
        self.st60cCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.tabC = wx.Panel(self.pn44c,-1,wx.Point(269,3),wx.Size(75,15))
        self.tabC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCCCCC = wx.StaticText(self.tabC,-1,"",wx.Point(4,0),wx.Size(64,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCCCCC.SetLabel("compressed")
        self.st60cCCCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.tabCCCC = wx.Panel(self.pn44c,-1,wx.Point(458,3),wx.Size(80,15))
        self.tabCCCC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCCCCCCC = wx.StaticText(self.tabCCCC,-1,"",wx.Point(4,0),wx.Size(74,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCCCCCCC.SetLabel("documents")
        self.st60cCCCCCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.tabCC = wx.Panel(self.pn44c,-1,wx.Point(347,3),wx.Size(40,15))
        self.tabCC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60cCCCCCCC = wx.StaticText(self.tabCC,-1,"",wx.Point(4,0),wx.Size(34,13),wx.ST_NO_AUTORESIZE)
        self.st60cCCCCCCC.SetLabel("xxx")
        self.st60cCCCCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.tabCCC = wx.Panel(self.pn44c,-1,wx.Point(385,3),wx.Size(55,15))
        self.tabCCC.SetBackgroundColour(wx.Colour(205,205,205))
        self.st60tab = wx.StaticText(self.tabCCC,-1,"",wx.Point(4,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st60tab.SetLabel("other")
        self.st60tab.SetForegroundColour(wx.Colour(0,0,0))
        self.pn9cC = wx.Panel(self,-1,wx.Point(0,403),wx.Size(10,28))
        self.pn9cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9cC_VwXEvOnEraseBackground)
        self.pn10cC = wx.Panel(self,-1,wx.Point(10,141),wx.Size(20,28))
        self.pn10cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn10cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10cC_VwXEvOnEraseBackground)
        self.bm159c = wx.StaticBitmap(self.pn10cC,-1,self.bm159cImg0,wx.Point(3,3),wx.Size(16,16))
        self.bm159c.SetBackgroundColour(wx.Colour(255,255,255))
        self.st158c = wx.StaticText(self.pn10cC,-1,"",wx.Point(1,1),wx.Size(279,14),wx.ST_NO_AUTORESIZE)
        self.st158c.SetLabel("add friend")
        self.st158c.SetForegroundColour(wx.Colour(0,0,0))
        self.st158c.SetBackgroundColour(wx.Colour(255,255,255))
        self.pn11cC = wx.Panel(self,-1,wx.Point(433,399),wx.Size(190,28))
        self.pn11cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11cC_VwXEvOnEraseBackground)
        self.st162c = wx.StaticText(self.pn48c,-1,"",wx.Point(8,23),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st162c.SetLabel("  video")
        self.st163c = wx.StaticText(self.pn48c,-1,"",wx.Point(8,4),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st163c.SetLabel("  all")
        self.chc166c = wx.Choice(self.pn48c,-1,wx.Point(8,78),wx.Size(106,21),[r'compressed',r'documents',r'xxx',r'other'])
        self.chc166c.SetBackgroundColour(wx.Colour(219,219,219))
        self.st160cC = wx.StaticText(self.pn48c,-1,"",wx.Point(8,57),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st160cC.SetLabel("  pictures")
        self.lno175c = wx.StaticLine(self.pn48c,-1,wx.Point(0,0),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.lno176c = wx.StaticLine(self.pn48c,-1,wx.Point(0,0),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.lno177c = wx.StaticLine(self.pn48c,-1,wx.Point(0,0),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.st163cC = wx.StaticText(self.pn48c,-1,"",wx.Point(564,6),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st163cC.SetLabel("  all")
        self.lno175cC = wx.StaticLine(self.pn48c,-1,wx.Point(533,23),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.st162cC = wx.StaticText(self.pn48c,-1,"",wx.Point(533,25),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st162cC.SetLabel("  video")
        self.lno176cC = wx.StaticLine(self.pn48c,-1,wx.Point(533,42),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.st160cCC = wx.StaticText(self.pn48c,-1,"",wx.Point(533,44),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st160cCC.SetLabel("  audio")
        self.lno177cC = wx.StaticLine(self.pn48c,-1,wx.Point(533,61),wx.Size(1,2),wx.LI_HORIZONTAL)
        self.st160cCCbh = wx.StaticText(self.pn48c,-1,"",wx.Point(120,61),wx.Size(86,16),wx.ST_NO_AUTORESIZE)
        self.st160cCCbh.SetLabel("  pictures")
        self.chc166cC = wx.Choice(self.pn48c,-1,wx.Point(533,80),wx.Size(106,21),[r'compressed',r'documents',r'xxx',r'other'])
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz8s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz8sC = wx.BoxSizer(wx.HORIZONTAL)
        self.tabsCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz14sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz170s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz161s = wx.BoxSizer(wx.VERTICAL)
        self.sz161sC = wx.BoxSizer(wx.VERTICAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCsd = wx.BoxSizer(wx.HORIZONTAL)
        self.sz61sCCCCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz157s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz8s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn48c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz3s.Add(self.pn44c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz3s.Add(self.sz8sC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn9c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.SetItemMinSize(self.pn10c,20,10)
        self.sz8s.Add(self.pn11c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn9cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn10cC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.SetItemMinSize(self.pn10cC,20,10)
        self.sz8sC.Add(self.pn11cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add([6,18],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC2C,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.tab,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC2CC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.pn39cCC2CCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.tabC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.tabCCCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.tabCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCC.Add(self.tabCCC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz61sC.Add(self.st60c,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCC.Add(self.st60cCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCC.Add(self.st60cCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCCC.Add(self.st60cCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz14sCC.Add([5,92],0,wx.TOP|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14sCC.Add(self.sz161s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14sCC.Add(self.sz161sC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14sCC.Add([213,92],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14sCC.Add(self.sz170s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz170s.Add(self.tx171c,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,5)
        self.sz170s.Add(self.bt172c,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,5)
        self.sz161s.Add(self.st163c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161s.Add(self.lno175c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161s.Add(self.st162c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161s.Add(self.lno176c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161s.Add(self.st160c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161s.Add(self.lno177c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161s.Add(self.st160cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161s.Add(self.chc166c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161sC.Add(self.st163cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161sC.Add(self.lno175cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161sC.Add(self.st162cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161sC.Add(self.lno176cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161sC.Add(self.st160cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161sC.Add(self.lno177cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz161sC.Add(self.st160cCCbh,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz161sC.Add(self.chc166cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCCCC.Add(self.st60cCCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCCCCC.Add(self.st60cCCCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCCCCCC.Add(self.st60cCCCCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCsd.Add(self.st60tab,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz61sCCCCCCCC.Add(self.st60cCCCCCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz157s.Add(self.bm159c,0,wx.FIXED_MINSIZE,3)
        self.sz157s.Add(self.st158c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,1)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn44c.SetSizer(self.tabsCC);self.pn44c.SetAutoLayout(1);self.pn44c.Layout();
        self.pn39cCC.SetSizer(self.sz61sC);self.pn39cCC.SetAutoLayout(1);self.pn39cCC.Layout();
        self.pn39cCC2C.SetSizer(self.sz61sCC);self.pn39cCC2C.SetAutoLayout(1);self.pn39cCC2C.Layout();
        self.pn39cCC2CC.SetSizer(self.sz61sCCC);self.pn39cCC2CC.SetAutoLayout(1);self.pn39cCC2CC.Layout();
        self.pn39cCC2CCC.SetSizer(self.sz61sCCCC);self.pn39cCC2CCC.SetAutoLayout(1);self.pn39cCC2CCC.Layout();
        self.pn48c.SetSizer(self.sz14sCC);self.pn48c.SetAutoLayout(1);self.pn48c.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.tab.SetSizer(self.sz61sCCCCC);self.tab.SetAutoLayout(1);self.tab.Layout();
        self.tabC.SetSizer(self.sz61sCCCCCC);self.tabC.SetAutoLayout(1);self.tabC.Layout();
        self.tabCC.SetSizer(self.sz61sCCCCCCC);self.tabCC.SetAutoLayout(1);self.tabCC.Layout();
        self.tabCCC.SetSizer(self.sz61sCsd);self.tabCCC.SetAutoLayout(1);self.tabCCC.Layout();
        self.tabCCCC.SetSizer(self.sz61sCCCCCCCC);self.tabCCCC.SetAutoLayout(1);self.tabCCCC.Layout();
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


    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[6f2]Code event VwX...Don't modify[6f2]#
        #add your code here
        event.Skip()

        return #end function


    def pn11c_VwXEvOnEraseBackground(self,event): #init function
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
