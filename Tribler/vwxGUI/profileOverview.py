# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from standardPager import *
#[inc]add your include files here

#[inc]end your include

class profileOverview(wx.Panel):
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
        self.fileImgBuf=[None] * 1
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.pn10cImg0=self.fileImgBuf[0];
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.orange_top_left = bgPanel(self, -1, wx.Point(0,0), wx.Size(10,21))
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(20,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(194,17),wx.ST_NO_AUTORESIZE)
        self.st64c.SetForegroundColour(wx.Colour(255,255,255))
        self.orange_top_right = bgPanel(self, -1, wx.Point(613,0), wx.Size(10,21))
        self.st219c = wx.StaticText(self,-1,"",wx.Point(0,33),wx.Size(623,18),wx.ST_NO_AUTORESIZE)
        self.st219c.SetLabel("   Profile")
        self.st219c.SetFont(wx.Font(12,74,90,90,0,"Verdana"))
        self.st219c.SetForegroundColour(wx.Colour(255,255,255))
        self.st219c.SetBackgroundColour(wx.Colour(0,0,0))
        self.thumb = bgPanel(self, -1, wx.Point(10,63), wx.Size(80,80))
        self.st227c = wx.StaticText(self,-1,"",wx.Point(106,69),wx.Size(94,13),wx.ST_NO_AUTORESIZE)
        self.st227c.SetLabel("nickname:")
        self.fdsfds = wx.StaticText(self,-1,"",wx.Point(106,85),wx.Size(94,18),wx.ST_NO_AUTORESIZE)
        self.fdsfds.SetLabel("e-mail address:")
        self.st229c = wx.StaticText(self,-1,"",wx.Point(206,69),wx.Size(169,13),wx.ST_NO_AUTORESIZE)
        self.st229c.SetLabel("Maarten")
        self.st230c = wx.StaticText(self,-1,"",wx.Point(206,85),wx.Size(169,18),wx.ST_NO_AUTORESIZE)
        self.st230c.SetLabel("maartentenbrinke@gmail.com")
        self.st219cC = wx.StaticText(self,-1,"",wx.Point(0,161),wx.Size(617,18),wx.ST_NO_AUTORESIZE)
        self.st219cC.SetLabel("   Statistics")
        self.st219cC.SetFont(wx.Font(12,74,90,90,0,"Verdana"))
        self.st219cC.SetForegroundColour(wx.Colour(255,255,255))
        self.st219cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn242c = wx.Panel(self,-1,wx.Point(0,191),wx.Size(623,85))
        self.pn242c.SetBackgroundColour(wx.Colour(203,203,203))
        self.perf = bgPanel(self.pn242c, -1, wx.Point(15,15), wx.Size(45,55))
        self.st245c = wx.StaticText(self.pn242c,-1,"",wx.Point(63,48),wx.Size(264,26),wx.ST_NO_AUTORESIZE)
        self.st245c.SetLabel("overall performance")
        self.st245c.SetFont(wx.Font(14,74,90,90,0,"Verdana"))
        self.bgPanel246c = bgPanel(self.pn242c, -1, wx.Point(370,10), wx.Size(55,55))
        self.pn248c = wx.Panel(self,-1,wx.Point(0,299),wx.Size(623,60))
        self.pn248c.SetBackgroundColour(wx.Colour(203,203,203))
        self.bgPanel247cC = bgPanel(self.pn248c, -1, wx.Point(15,15), wx.Size(30,30))
        self.st241cC = wx.StaticText(self.pn248c,-1,"",wx.Point(59,24),wx.Size(239,16),wx.ST_NO_AUTORESIZE)
        self.st241cC.SetLabel("Quality of tribler recommendations")
        self.orange_bottom_left = bgPanel(self, -1, wx.Point(0,399), wx.Size(10,28))
        self.orange_bottom_center = bgPanel(self, -1, wx.Point(10,399), wx.Size(20,20))
        self.pagerBottomRight = bgPanel(self, -1, wx.Point(600,403), wx.Size(271,28))
        self.standardPager = standardPager(self.pagerBottomRight,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(25,5,238,23)
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.profile = wx.BoxSizer(wx.HORIZONTAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz211s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz223s = wx.BoxSizer(wx.VERTICAL)
        self.sz226s = wx.BoxSizer(wx.VERTICAL)
        self.sz243s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz254s = wx.BoxSizer(wx.VERTICAL)
        self.qualityC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256s = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219c,0,wx.TOP|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.profile,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.pn242c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,18)
        self.sz3s.Add(self.pn248c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add([617,35],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.footer,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.orange_top_left,0,wx.FIXED_MINSIZE,3)
        self.header.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.pn10c,20,10)
        self.header.Add(self.orange_top_right,0,wx.FIXED_MINSIZE,3)
        self.footer.Add(self.orange_bottom_left,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.orange_bottom_center,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.pagerBottomRight,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.profile.Add(self.thumb,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.profile.Add(self.sz223s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.profile.Add(self.sz226s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz211s.Add([25,28],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz211s.Add(self.standardPager,1,wx.TOP|wx.EXPAND,5)
        self.sz211s.Add([8,28],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz223s.Add(self.st227c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz223s.Add(self.fdsfds,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz226s.Add(self.st229c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz226s.Add(self.st230c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz243s.Add(self.perf,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,15)
        self.sz243s.Add(self.sz254s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz243s.Add(self.bgPanel246c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,15)
        self.sz254s.Add([270,45],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz254s.Add(self.st245c,0,wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,6)
        self.qualityC.Add(self.bgPanel247cC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,15)
        self.qualityC.Add(self.sz256s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256s.Add([255,25],0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256s.Add(self.st241cC,0,wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,11)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pagerBottomRight.SetSizer(self.sz211s);self.pagerBottomRight.SetAutoLayout(1);self.pagerBottomRight.Layout();
        self.pn242c.SetSizer(self.sz243s);self.pn242c.SetAutoLayout(1);self.pn242c.Layout();
        self.pn248c.SetSizer(self.qualityC);self.pn248c.SetAutoLayout(1);self.pn248c.Layout();
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
        #[175]Code event VwX...Don't modify[175]#
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
        #[174]Code VwX...Don't modify[174]#
        #add your code here

        return #end function

#[win]end your code
