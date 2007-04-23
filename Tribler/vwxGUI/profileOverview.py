# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from standardPager import *
#[inc]add your include files here

#[inc]end your include

class profileOverview(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(625,600),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.thumb = bgPanel(self, -1, wx.Point(15,63), wx.Size(80,80))
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
        self.perfL3 = bgPanel(self.pn242c, -1, wx.Point(15,15), wx.Size(45,55))
        self.st245c = wx.StaticText(self.pn242c,-1,"",wx.Point(69,48),wx.Size(264,26),wx.ST_NO_AUTORESIZE)
        self.st245c.SetLabel("overall performance")
        self.st245c.SetFont(wx.Font(14,74,90,90,0,"Verdana"))
        self.bgPanel246c = bgPanel(self.pn242c, -1, wx.Point(370,10), wx.Size(55,55))
        self.quality = wx.Panel(self,-1,wx.Point(0,299),wx.Size(623,40))
        self.quality.SetBackgroundColour(wx.Colour(203,203,203))
        self.perfM0 = [None] * 3
        self.perfM0[1] = bgPanel(self.quality, -1, wx.Point(15,5), wx.Size(25,30))
        self.perfM0[1].index=1
        self.st241cC = wx.StaticText(self.quality,-1,"",wx.Point(48,18),wx.Size(419,16),wx.ST_NO_AUTORESIZE)
        self.st241cC.SetLabel("Quality of tribler recommendations")
        self.st241cC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.orange_bottom_left = bgPanel(self, -1, wx.Point(0,399), wx.Size(10,28))
        self.orange_bottom_center = bgPanel(self, -1, wx.Point(10,399), wx.Size(20,20))
        self.pagerBottomRight = bgPanel(self, -1, wx.Point(600,403), wx.Size(271,28))
        self.standardPager = standardPager(self.pagerBottomRight,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(25,5,238,23)
        self.pn248cC = wx.Panel(self,-1,wx.Point(3,405),wx.Size(623,40))
        self.pn248cC.SetBackgroundColour(wx.Colour(255,255,255))
        self.perfM1 = [None] * 3
        self.perfM1[1] = bgPanel(self.pn248cC, -1, wx.Point(15,5), wx.Size(25,30))
        self.perfM1[1].index=1
        self.st241cCC = wx.StaticText(self.pn248cC,-1,"",wx.Point(48,18),wx.Size(419,16),wx.ST_NO_AUTORESIZE)
        self.st241cCC.SetLabel("Discovered persons similar to your taste")
        self.st241cCC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.pn248cCC = wx.Panel(self,-1,wx.Point(3,405),wx.Size(623,40))
        self.pn248cCC.SetBackgroundColour(wx.Colour(203,203,203))
        self.perfM2 = bgPanel(self.pn248cCC, -1, wx.Point(15,5), wx.Size(25,30))
        self.st241cCCC = wx.StaticText(self.pn248cCC,-1,"",wx.Point(48,18),wx.Size(379,16),wx.ST_NO_AUTORESIZE)
        self.st241cCCC.SetLabel("Discovered files that fit your taste")
        self.st241cCCC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.pn248cCCC = wx.Panel(self,-1,wx.Point(0,419),wx.Size(623,40))
        self.pn248cCCC.SetBackgroundColour(wx.Colour(255,255,255))
        self.perfM3 = bgPanel(self.pn248cCCC, -1, wx.Point(15,5), wx.Size(25,30))
        self.st241cCCCC = wx.StaticText(self.pn248cCCC,-1,"",wx.Point(48,18),wx.Size(349,16),wx.ST_NO_AUTORESIZE)
        self.st241cCCCC.SetLabel("Maximum download speed\r\n")
        self.st241cCCCC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.pn248cCCCC = wx.Panel(self,-1,wx.Point(3,475),wx.Size(623,40))
        self.pn248cCCCC.SetBackgroundColour(wx.Colour(203,203,203))
        self.perfM5 = bgPanel(self.pn248cCCCC, -1, wx.Point(15,5), wx.Size(25,30))
        self.st241cCCCCC = wx.StaticText(self.pn248cCCCC,-1,"",wx.Point(48,18),wx.Size(339,16),wx.ST_NO_AUTORESIZE)
        self.st241cCCCCC.SetLabel("Social Presence")
        self.st241cCCCCC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
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
        self.qualitySizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256s = wx.BoxSizer(wx.VERTICAL)
        self.qualityCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256sC = wx.BoxSizer(wx.VERTICAL)
        self.qualityCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256sCC = wx.BoxSizer(wx.VERTICAL)
        self.qualityCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256sCCC = wx.BoxSizer(wx.VERTICAL)
        self.qualityCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz256sCCCC = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219c,0,wx.TOP|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.profile,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.pn242c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,18)
        self.sz3s.Add(self.quality,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add(self.pn248cC,0,wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add(self.pn248cCC,0,wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add(self.pn248cCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add(self.pn248cCCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,23)
        self.sz3s.Add([617,65],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
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
        self.sz243s.Add(self.perfL3,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,15)
        self.sz243s.Add(self.sz254s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz243s.Add(self.bgPanel246c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,15)
        self.sz254s.Add([270,45],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz254s.Add(self.st245c,0,wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,6)
        self.qualitySizer.Add([15,38],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualitySizer.Add(self.perfM0[1],0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualitySizer.Add(self.sz256s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256s.Add(self.st241cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.qualityCC.Add([15,38],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualityCC.Add(self.perfM1[1],0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualityCC.Add(self.sz256sC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256sC.Add(self.st241cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.qualityCCC.Add([15,38],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualityCCC.Add(self.perfM2,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualityCCC.Add(self.sz256sCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256sCC.Add(self.st241cCCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.qualityCCCC.Add([15,38],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualityCCCC.Add(self.perfM3,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualityCCCC.Add(self.sz256sCCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256sCCC.Add(self.st241cCCCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.qualityCCCCC.Add([15,38],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualityCCCCC.Add(self.perfM5,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualityCCCCC.Add(self.sz256sCCCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz256sCCCC.Add(self.st241cCCCCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pagerBottomRight.SetSizer(self.sz211s);self.pagerBottomRight.SetAutoLayout(1);self.pagerBottomRight.Layout();
        self.pn242c.SetSizer(self.sz243s);self.pn242c.SetAutoLayout(1);self.pn242c.Layout();
        self.quality.SetSizer(self.qualitySizer);self.quality.SetAutoLayout(1);self.quality.Layout();
        self.pn248cC.SetSizer(self.qualityCC);self.pn248cC.SetAutoLayout(1);self.pn248cC.Layout();
        self.pn248cCC.SetSizer(self.qualityCCC);self.pn248cCC.SetAutoLayout(1);self.pn248cCC.Layout();
        self.pn248cCCC.SetSizer(self.qualityCCCC);self.pn248cCCC.SetAutoLayout(1);self.pn248cCCC.Layout();
        self.pn248cCCCC.SetSizer(self.qualityCCCCC);self.pn248cCCCC.SetAutoLayout(1);self.pn248cCCCC.Layout();
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
