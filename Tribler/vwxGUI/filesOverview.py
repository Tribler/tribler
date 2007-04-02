# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from filesGrid import *
from standardPager import *
#[inc]add your include files here

#[inc]end your include

class filesOverview(wx.Panel):
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
        self.pn10c = wx.Panel(self,-1,wx.Point(135,0),wx.Size(20,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(269,15),wx.ST_NO_AUTORESIZE)
        self.st64c.SetLabel("Files")
        self.st64c.SetForegroundColour(wx.Colour(255,255,255))
        self.st64c.SetBackgroundColour(wx.Colour(255,51,0))
        self.orange_top_right = bgPanel(self, -1, wx.Point(613,0), wx.Size(10,21))
        self.pn214c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(623,35))
        self.pn214c.SetBackgroundColour(wx.Colour(153,153,153))
        self.chc215c = wx.Choice(self.pn214c,-1,wx.Point(134,3),wx.Size(120,21),[r'most popular',r'top rated',r'recommended',r'from network'])
        self.chc215c.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.chc215cCC = wx.Choice(self.pn214c,-1,wx.Point(260,3),wx.Size(120,21),[r'today',r'this week',r'this month',r'all time'])
        self.chc215cCC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.chc215cC = wx.Choice(self.pn214c,-1,wx.Point(8,3),wx.Size(120,21),[r'video',r'audio',r'pictures',r'other',r'xxx'])
        self.chc215cC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.filesGrid = filesGrid(self,-1,wxDefaultPosition,wxDefaultSize)
        self.filesGrid.SetDimensions(10,66,623,10)
        self.orange_bottom_left = bgPanel(self, -1, wx.Point(0,400), wx.Size(10,28))
        self.orange_bottom_center = bgPanel(self, -1, wx.Point(10,400), wx.Size(20,20))
        self.pagerBottomRight = bgPanel(self, -1, wx.Point(352,400), wx.Size(271,28))
        self.standardPager = standardPager(self.pagerBottomRight,-1,wxDefaultPosition,wxDefaultSize)
        self.standardPager.SetDimensions(25,5,238,23)
        self.vertical = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.footer = wx.BoxSizer(wx.HORIZONTAL)
        self.size_title = wx.BoxSizer(wx.HORIZONTAL)
        self.sz211s = wx.BoxSizer(wx.HORIZONTAL)
        self.horizontal = wx.BoxSizer(wx.HORIZONTAL)
        self.sz221s = wx.BoxSizer(wx.HORIZONTAL)
        self.vertical.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical.Add(self.pn214c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical.Add(self.filesGrid,1,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vertical.Add(self.footer,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.orange_top_left,0,wx.FIXED_MINSIZE,3)
        self.header.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.pn10c,20,10)
        self.header.Add(self.orange_top_right,0,wx.FIXED_MINSIZE,3)
        self.footer.Add(self.orange_bottom_left,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.orange_bottom_center,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.footer.Add(self.pagerBottomRight,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.size_title.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz211s.Add([25,28],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz211s.Add(self.standardPager,1,wx.TOP|wx.EXPAND,5)
        self.sz211s.Add([8,28],0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.horizontal.Add([8,33],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.horizontal.Add(self.sz221s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.horizontal.Add([10,33],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz221s.Add(self.chc215cC,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz221s.Add(self.chc215c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz221s.Add(self.chc215cCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.vertical);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.size_title);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pagerBottomRight.SetSizer(self.sz211s);self.pagerBottomRight.SetAutoLayout(1);self.pagerBottomRight.Layout();
        self.pn214c.SetSizer(self.horizontal);self.pn214c.SetAutoLayout(1);self.pn214c.Layout();
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

    def bla(self):
        pass
        



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
