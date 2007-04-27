# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from tribler_topButton import *
from perfBar import SmallPerfBar
from standardPager import *
from perfBar import BigPerfBar
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
        self.st227c = wx.StaticText(self,-1,"",wx.Point(110,69),wx.Size(64,23),wx.ST_NO_AUTORESIZE)
        self.st227c.SetLabel("nickname:")
        self.myNameField = wx.StaticText(self,-1,"",wx.Point(202,66),wx.Size(169,23),wx.ST_NO_AUTORESIZE)
        self.myNameField.SetLabel("Maarten")
        self.myNameField.SetFont(wx.Font(11,74,90,92,0,"Tahoma"))
        self.st219cC = wx.StaticText(self,-1,"",wx.Point(0,155),wx.Size(617,18),wx.ST_NO_AUTORESIZE)
        self.st219cC.SetLabel("   Performance")
        self.st219cC.SetFont(wx.Font(12,74,90,90,0,"Verdana"))
        self.st219cC.SetForegroundColour(wx.Colour(255,255,255))
        self.st219cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.bgPanel_Overall = tribler_topButton(self, -1, wx.Point(0,202), wx.Size(600,85))
        self.bgPanel_Overall.SetBackgroundColour(wx.Colour(255,255,255))
        self.bgPanel_Quality = tribler_topButton(self, -1, wx.Point(0,276), wx.Size(417,40))
        self.bgPanel_Quality.SetBackgroundColour(wx.Colour(203,203,203))
        self.perf_Quality = SmallPerfBar(self.bgPanel_Quality,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Quality.SetDimensions(15,5,25,30)
        self.text_Quality = wx.StaticText(self.bgPanel_Quality,-1,"",wx.Point(45,15),wx.Size(335,25),wx.ST_NO_AUTORESIZE)
        self.text_Quality.SetLabel("Quality of tribler recommendations")
        self.text_Quality.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.text_Quality.SetBackgroundColour(wx.Colour(203,203,203))
        self.bgPanel_Files = tribler_topButton(self, -1, wx.Point(0,316), wx.Size(20,40))
        self.perf_Files = SmallPerfBar(self.bgPanel_Files,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Files.SetDimensions(15,5,25,30)
        self.text_Files = wx.StaticText(self.bgPanel_Files,-1,"",wx.Point(45,15),wx.Size(379,16),wx.ST_NO_AUTORESIZE)
        self.text_Files.SetLabel("Discovered files that fit your taste")
        self.text_Files.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.text_Files.SetBackgroundColour(wx.Colour(203,203,203))
        self.bgPanel_Persons = tribler_topButton(self, -1, wx.Point(3,359), wx.Size(20,40))
        self.perf_Persons = SmallPerfBar(self.bgPanel_Persons,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Persons.SetDimensions(15,5,25,30)
        self.text_Persons = wx.StaticText(self.bgPanel_Persons,-1,"",wx.Point(45,15),wx.Size(419,16),wx.ST_NO_AUTORESIZE)
        self.text_Persons.SetLabel("Discovered persons similar to your taste")
        self.text_Persons.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.text_Persons.SetBackgroundColour(wx.Colour(203,203,203))
        self.bgPanel_Download = tribler_topButton(self, -1, wx.Point(3,365), wx.Size(20,40))
        self.perf_Download = SmallPerfBar(self.bgPanel_Download,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Download.SetDimensions(15,5,25,30)
        self.text_Download = wx.StaticText(self.bgPanel_Download,-1,"",wx.Point(45,15),wx.Size(384,23),wx.ST_NO_AUTORESIZE)
        self.text_Download.SetLabel("Maximum download speed\r\n")
        self.text_Download.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.text_Download.SetBackgroundColour(wx.Colour(203,203,203))
        self.bgPanel_Presence = tribler_topButton(self, -1, wx.Point(3,391), wx.Size(20,40))
        self.perf_Presence = SmallPerfBar(self.bgPanel_Presence,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Presence.SetDimensions(15,5,25,30)
        self.text_Presence = wx.StaticText(self.bgPanel_Presence,-1,"",wx.Point(45,15),wx.Size(339,16),wx.ST_NO_AUTORESIZE)
        self.text_Presence.SetLabel("Social presence")
        self.text_Presence.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.text_Presence.SetBackgroundColour(wx.Colour(203,203,203))
        self.orange_bottom_left = bgPanel(self, -1, wx.Point(0,399), wx.Size(10,28))
        self.orange_bottom_center = bgPanel(self, -1, wx.Point(10,399), wx.Size(20,20))
        self.pagerBottomRight = bgPanel(self, -1, wx.Point(600,403), wx.Size(271,28))
        self.standardPager = standardPager(self.pagerBottomRight,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(25,5,238,23)
        self.icon_Overall = wx.Panel(self,-1,wx.Point(600,239),wx.Size(20,40))
        self.icon_Overall.SetBackgroundColour(wx.Colour(230,230,230))
        self.text_Overall = wx.StaticText(self.bgPanel_Overall,-1,"",wx.Point(91,49),wx.Size(439,26),wx.ST_NO_AUTORESIZE)
        self.text_Overall.SetLabel("overall performance")
        self.text_Overall.SetFont(wx.Font(14,74,90,90,0,"Verdana"))
        self.text_Overall.SetBackgroundColour(wx.Colour(230,230,230))
        self.perf_Overall = BigPerfBar(self.bgPanel_Overall,-1,wxDefaultPosition,wxDefaultSize)
        self.perf_Overall.SetDimensions(15,0,70,85)
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.profile = wx.BoxSizer(wx.HORIZONTAL)
        self.sz329s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz211s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz223s = wx.BoxSizer(wx.VERTICAL)
        self.sz226s = wx.BoxSizer(wx.VERTICAL)
        self.qualitySizer = wx.BoxSizer(wx.HORIZONTAL)
        self.filesSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.personsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.presenceSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hori = wx.BoxSizer(wx.HORIZONTAL)
        self.sz254sC = wx.BoxSizer(wx.VERTICAL)
        self.sz332s = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219c,0,wx.TOP|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.profile,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st219cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.sz3s.Add(self.sz329s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,29)
        self.sz3s.Add([623,29],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.bgPanel_Quality,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.bgPanel_Files,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz3s.Add(self.bgPanel_Persons,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz3s.Add(self.bgPanel_Download,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz3s.Add(self.bgPanel_Presence,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz3s.Add([623,46],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
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
        self.sz329s.Add(self.bgPanel_Overall,0,wx.FIXED_MINSIZE,18)
        self.sz329s.Add(self.sz332s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz211s.Add([25,28],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz211s.Add(self.standardPager,1,wx.TOP|wx.EXPAND,5)
        self.sz211s.Add([8,28],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz223s.Add(self.st227c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz226s.Add(self.myNameField,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualitySizer.Add([15,40],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.qualitySizer.Add(self.perf_Quality,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.qualitySizer.Add(self.text_Quality,0,wx.TOP|wx.FIXED_MINSIZE,15)
        self.filesSizer.Add([15,40],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.filesSizer.Add(self.perf_Files,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.filesSizer.Add(self.text_Files,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.personsSizer.Add([15,40],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.personsSizer.Add(self.perf_Persons,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.personsSizer.Add(self.text_Persons,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.downloadSizer.Add([15,40],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add(self.perf_Download,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.downloadSizer.Add(self.text_Download,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.presenceSizer.Add([15,40],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.presenceSizer.Add(self.perf_Presence,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.presenceSizer.Add(self.text_Presence,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,15)
        self.hori.Add(self.perf_Overall,0,wx.LEFT|wx.FIXED_MINSIZE,15)
        self.hori.Add(self.sz254sC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.hori.Add([70,85],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz254sC.Add([445,49],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz254sC.Add(self.text_Overall,0,wx.LEFT|wx.BOTTOM|wx.FIXED_MINSIZE,6)
        self.sz332s.Add([23,37],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz332s.Add(self.icon_Overall,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz332s.Add([23,8],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pagerBottomRight.SetSizer(self.sz211s);self.pagerBottomRight.SetAutoLayout(1);self.pagerBottomRight.Layout();
        self.bgPanel_Quality.SetSizer(self.qualitySizer);self.bgPanel_Quality.SetAutoLayout(1);self.bgPanel_Quality.Layout();
        self.bgPanel_Files.SetSizer(self.filesSizer);self.bgPanel_Files.SetAutoLayout(1);self.bgPanel_Files.Layout();
        self.bgPanel_Persons.SetSizer(self.personsSizer);self.bgPanel_Persons.SetAutoLayout(1);self.bgPanel_Persons.Layout();
        self.bgPanel_Download.SetSizer(self.downloadSizer);self.bgPanel_Download.SetAutoLayout(1);self.bgPanel_Download.Layout();
        self.bgPanel_Presence.SetSizer(self.presenceSizer);self.bgPanel_Presence.SetAutoLayout(1);self.bgPanel_Presence.Layout();
        self.bgPanel_Overall.SetSizer(self.hori);self.bgPanel_Overall.SetAutoLayout(1);self.bgPanel_Overall.Layout();
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
        #[55f]Code event VwX...Don't modify[55f]#
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
        #[55e]Code VwX...Don't modify[55e]#
        #add your code here

        return #end function

#[win]end your code
