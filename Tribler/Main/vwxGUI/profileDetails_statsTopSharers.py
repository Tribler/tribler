# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from bgPanel import ImagePanel
#[inc]add your include files here

#[inc]end your include

class profileDetails_statsTopSharers(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,710),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.titleField = wx.StaticText(self.titlePanel,-1,"",wx.Point(0,5),wx.Size(280,15),wx.ST_NO_AUTORESIZE)
        self.titleField.SetLabel("top 10 Tribler Uploaders")
        self.titleField.SetForegroundColour(wx.Colour(255,255,255))
        self.titleField.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(275,3), wx.Size(10,21))
        self.details = wx.Panel(self,-1,wx.Point(0,21),wx.Size(298,645))
        self.details.SetBackgroundColour(wx.Colour(255,255,255))
        self.st371c = wx.StaticText(self.details,-1,"",wx.Point(22,10),wx.Size(286,18),wx.ST_NO_AUTORESIZE)
        self.st371c.SetLabel("Stats for only the Tribler network:")
        self.st371c.SetFont(wx.Font(9,74,90,90,0,"Verdana"))
        self.descriptionField0 = wx.StaticText(self.details,-1,"",wx.Point(14,42),wx.Size(282,478))
        self.descriptionField0.SetLabel("no info available yet\r\n\r\n\r\n\r\n	\r\n")
        self.descriptionField0.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.howToImprove = wx.StaticText(self.details,-1,"",wx.Point(12,522),wx.Size(284,18),wx.ST_NO_AUTORESIZE)
        self.howToImprove.SetLabel("Your exchanges with other Tribler users:")
        self.howToImprove.SetFont(wx.Font(9,74,90,90,0,"Verdana"))
        self.white_bottom = bgPanel(self, -1, wx.Point(0,221), wx.Size(300,5))
        self.infoIcon = ImagePanel(self.details,-1,wxDefaultPosition,wxDefaultSize)
        self.infoIcon.SetDimensions(10,14,8,8)
        self.infoIcon.SetToolTipString('Tribler is a special network on top of the overall network.\\nThese figures shows the top 10 uploaders within the Tribler network.')
        self.st227cC = wx.StaticText(self.details,-1,"",wx.Point(11,179),wx.Size(144,18),wx.ST_NO_AUTORESIZE)
        self.st227cC.SetLabel("total downloaded:")
        self.st227cC.SetFont(wx.Font(9,74,90,92,0,"Verdana"))
        self.downloadedNumberT = wx.StaticText(self.details,-1,"",wx.Point(157,179),wx.Size(99,18),wx.ST_NO_AUTORESIZE)
        self.downloadedNumberT.SetLabel("_")
        self.downloadedNumberT.SetFont(wx.Font(9,74,90,92,0,"Verdana"))
        self.st227cCC = wx.StaticText(self.details,-1,"",wx.Point(11,199),wx.Size(144,18),wx.ST_NO_AUTORESIZE)
        self.st227cCC.SetLabel("total uploaded:")
        self.st227cCC.SetFont(wx.Font(9,74,90,92,0,"Verdana"))
        self.uploadedNumberT = wx.StaticText(self.details,-1,"",wx.Point(157,199),wx.Size(99,18),wx.ST_NO_AUTORESIZE)
        self.uploadedNumberT.SetLabel("_")
        self.uploadedNumberT.SetFont(wx.Font(9,74,90,92,0,"Verdana"))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.sz226s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz67s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz69s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz69sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3s.Add(self.details,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.header.Add(self.titlePanel,1,wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.titlePanel,20,10)
        self.header.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz226s.Add(self.titleField,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz184s.Add(self.sz67s,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add([290,8],0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.descriptionField0,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,14)
        self.vert_sz184s.Add(self.howToImprove,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,12)
        self.vert_sz184s.Add(self.sz69s,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,11)
        self.vert_sz184s.Add(self.sz69sC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,11)
        self.sz67s.Add(self.infoIcon,0,wx.TOP|wx.FIXED_MINSIZE,4)
        self.sz67s.Add(self.st371c,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz69s.Add(self.st227cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz69s.Add(self.downloadedNumberT,1,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz69sC.Add(self.st227cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,2)
        self.sz69sC.Add(self.uploadedNumberT,1,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,2)
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
        #[41a]Code event VwX...Don't modify[41a]#
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
        #[419]Code VwX...Don't modify[419]#
        #add your code here

        return #end function

#[win]end your code
