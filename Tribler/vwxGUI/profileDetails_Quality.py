# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
#[inc]add your include files here

#[inc]end your include

class pnl20346f(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,500),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.titlePanelImg0=self.fileImgBuf[0];
        self.Show(True)
        self.black_top_left = bgPanel(self, -1, wx.Point(3,3), wx.Size(10,21))
        self.titlePanel = wx.Panel(self,-1,wx.Point(13,3),wx.Size(280,21))
        self.titlePanel.SetForegroundColour(wx.Colour(255,255,255))
        self.titlePanel.SetBackgroundColour(wx.Colour(0,0,0))
        self.titlePanel.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtitlePanel_VwXEvOnEraseBackground)
        self.titleField = wx.StaticText(self.titlePanel,-1,"",wx.Point(0,3),wx.Size(280,18),wx.ST_NO_AUTORESIZE)
        self.titleField.SetLabel("Overall performance\r\n")
        self.titleField.SetForegroundColour(wx.Colour(255,255,255))
        self.titleField.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(275,3), wx.Size(10,21))
        self.details = wx.Panel(self,-1,wx.Point(0,21),wx.Size(300,348))
        self.details.SetBackgroundColour(wx.Colour(255,255,255))
        self.descriptionField = wx.StaticText(self.details,-1,"",wx.Point(6,6),wx.Size(284,223),wx.ST_NO_AUTORESIZE)
        self.descriptionField.SetLabel("You just have started using tribler. By using the different facets of tribler your overall performance will improve. In this way your status can grow from ‘starter’ to ‘leader’\r\n\r\n* Starter <<\r\n* Less then average\r\n* Runner up\r\n* Addict\r\n* Leader!")
        self.descriptionField.SetFont(wx.Font(8,74,93,90,0,"Verdana"))
        self.white_bottom = bgPanel(self, -1, wx.Point(3,475), wx.Size(300,5))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.sz226s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3s.Add(self.details,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.header.Add(self.titlePanel,1,wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.titlePanel,20,10)
        self.header.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz226s.Add(self.titleField,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add([290,8],0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.descriptionField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.titlePanel.SetSizer(self.sz226s);self.titlePanel.SetAutoLayout(1);self.titlePanel.Layout();
        self.details.SetSizer(self.vert_sz184s);self.details.SetAutoLayout(1);self.details.Layout();
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
    def VwXtitlePanel_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.titlePanel,self.titlePanelImg0,2)
        self.titlePanel_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def titlePanel_VwXEvOnEraseBackground(self,event): #init function
        #[617]Code event VwX...Don't modify[617]#
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
        #[616]Code VwX...Don't modify[616]#
        #add your code here

        return #end function

#[win]end your code
