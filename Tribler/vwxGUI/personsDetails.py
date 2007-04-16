# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from tribler_topButton import *
from btn_DetailsHeader import *
from tasteHeart import *
#[inc]add your include files here

#[inc]end your include

class personsDetails(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,420),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf=[None] * 2
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/5_160x90.jpg",wx.BITMAP_TYPE_JPEG)
        self.titlePanelImg0=self.fileImgBuf[0];
        self.thumbFieldImg0=self.fileImgBuf[1];
        self.Show(True)
        self.SetForegroundColour(wx.Colour(216,216,191))
        self.black_top_left = bgPanel(self, -1, wx.Point(0,0), wx.Size(10,21))
        self.titlePanel = wx.Panel(self,-1,wx.Point(13,525),wx.Size(280,21))
        self.titlePanel.SetForegroundColour(wx.Colour(255,255,255))
        self.titlePanel.SetBackgroundColour(wx.Colour(0,0,0))
        self.titlePanel.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtitlePanel_VwXEvOnEraseBackground)
        self.titleField = wx.StaticText(self.titlePanel,-1,"",wx.Point(0,3),wx.Size(280,18),wx.ST_NO_AUTORESIZE)
        self.titleField.SetLabel("Title\r\n")
        self.titleField.SetForegroundColour(wx.Colour(255,255,255))
        self.titleField.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(288,0), wx.Size(10,21))
        self.tabs = wx.Panel(self,-1,wx.Point(0,211),wx.Size(300,18))
        self.tabs.SetBackgroundColour(wx.Colour(0,0,0))
        self.info = tribler_topButton(self.tabs, -1, wx.Point(3,3), wx.Size(75,18))
        self.st230c = wx.StaticText(self.info,-1,"",wx.Point(4,1),wx.Size(64,13),wx.ST_NO_AUTORESIZE)
        self.st230c.SetLabel("info")
        self.st230c.SetBackgroundColour(wx.Colour(203,203,203))
        self.files = tribler_topButton(self.tabs, -1, wx.Point(81,3), wx.Size(75,18))
        self.st230cC = wx.StaticText(self.files,-1,"",wx.Point(4,1),wx.Size(64,13),wx.ST_NO_AUTORESIZE)
        self.st230cC.SetLabel("advanced")
        self.st230cC.SetBackgroundColour(wx.Colour(203,203,203))
        self.detailsC = wx.Panel(self,-1,wx.Point(0,145),wx.Size(298,238))
        self.detailsC.SetBackgroundColour(wx.Colour(255,255,255))
        self.st209cCCC = wx.StaticText(self.detailsC,-1,"",wx.Point(8,7),wx.Size(79,16),wx.ST_NO_AUTORESIZE)
        self.st209cCCC.SetLabel("fit to taste:")
        self.recommendationField = wx.StaticText(self.detailsC,-1,"",wx.Point(107,7),wx.Size(71,21),wx.ST_NO_AUTORESIZE)
        self.recommendationField.SetLabel("unknown")
        self.Desc = wx.StaticText(self.detailsC,-1,"",wx.Point(0,85),wx.Size(241,15),wx.ST_NO_AUTORESIZE)
        self.Desc.SetLabel("   Common files")
        self.Desc.SetBackgroundColour(wx.Colour(203,203,203))
        self.descriptionField = wx.StaticText(self.detailsC,-1,"",wx.Point(6,106),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.descriptionField.SetLabel("no common files available")
        self.descriptionField.SetFont(wx.Font(8,74,93,90,0,"Verdana"))
        self.Peop = btn_DetailsHeader(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.Peop.SetDimensions(0,179,20,20)
        self.st202cC = wx.StaticText(self.Peop,-1,"",wx.Point(10,0),wx.Size(204,18),wx.ST_NO_AUTORESIZE)
        self.st202cC.SetLabel("Also downloaded")
        self.st202cC.SetBackgroundColour(wx.Colour(203,203,203))
        self.peoplewhoField = wx.StaticText(self.detailsC,-1,"",wx.Point(6,186),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.peoplewhoField.SetLabel("no info available")
        self.peoplewhoField.SetFont(wx.Font(8,74,93,90,0,"Verdana"))
        self.white_bottom = bgPanel(self, -1, wx.Point(0,543), wx.Size(300,5))
        self.pn240c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(20,106))
        self.pn240c.SetBackgroundColour(wx.Colour(0,0,0))
        self.thumbField = wx.Panel(self.pn240c,-1,wx.Point(10,3),wx.Size(100,100))
        self.thumbField.SetBackgroundColour(wx.Colour(50,153,204))
        self.thumbField.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXthumbField_VwXEvOnEraseBackground)
        self.TasteHeart = TasteHeart(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.TasteHeart.SetDimensions(90,10,14,14)
        self.addAsFriend = tribler_topButton(self.detailsC, -1, wx.Point(191,7), wx.Size(55,55))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.headerC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz226s = wx.BoxSizer(wx.HORIZONTAL)
        self.tabsCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz237s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz238s = wx.BoxSizer(wx.VERTICAL)
        self.recommendationSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz241s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.headerC,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3s.Add(self.pn240c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.tabs,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.detailsC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.headerC.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.headerC.Add(self.titlePanel,1,wx.FIXED_MINSIZE,3)
        self.headerC.SetItemMinSize(self.titlePanel,20,10)
        self.headerC.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz226s.Add(self.titleField,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCCCC.Add(self.info,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.tabsCCCC.Add(self.files,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,8)
        self.vert_sz184s.Add(self.sz237s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.Desc,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.descriptionField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.vert_sz184s.Add(self.Peop,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add(self.peoplewhoField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz237s.Add(self.vert_sz238s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz237s.Add(self.downloadSizer,0,wx.TOP|wx.FIXED_MINSIZE,4)
        self.vert_sz238s.Add(self.recommendationSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.recommendationSizer.Add(self.st209cCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.TasteHeart,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.recommendationField,0,wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.downloadSizer.Add(self.addAsFriend,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz241s.Add([10,104],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz241s.Add(self.thumbField,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.titlePanel.SetSizer(self.sz226s);self.titlePanel.SetAutoLayout(1);self.titlePanel.Layout();
        self.tabs.SetSizer(self.tabsCCCC);self.tabs.SetAutoLayout(1);self.tabs.Layout();
        self.detailsC.SetSizer(self.vert_sz184s);self.detailsC.SetAutoLayout(1);self.detailsC.Layout();
        self.pn240c.SetSizer(self.sz241s);self.pn240c.SetAutoLayout(1);self.pn240c.Layout();
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
    def VwXthumbField_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.thumbField,self.thumbFieldImg0,0)
        self.thumbField_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def thumbField_VwXEvOnEraseBackground(self,event): #init function
        #[75f]Code event VwX...Don't modify[75f]#
        #add your code here
        event.Skip()

        return #end function


    def titlePanel_VwXEvOnEraseBackground(self,event): #init function
        #[32a]Code event VwX...Don't modify[32a]#
        #add your code here
        event.Skip()

        return #end function


    def pn9cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 40]Code event VwX...Don't modify[ 40]#
        #add your code here
        event.Skip()

        return #end function

    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[ 3c]Code event VwX...Don't modify[ 3c]#
        #add your code here
        event.Skip()

        return #end function

    def pn15cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 3f]Code event VwX...Don't modify[ 3f]#
        #add your code here
        event.Skip()

        return #end function

    def pn11cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 42]Code event VwX...Don't modify[ 42]#
        #add your code here
        event.Skip()

        return #end function

    def pn11c_VwXEvOnEraseBackground(self,event): #init function
        #[ 3e]Code event VwX...Don't modify[ 3e]#
        #add your code here
        event.Skip()

        return #end function

    def pn10cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 41]Code event VwX...Don't modify[ 41]#
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
        #[ 3b]Code VwX...Don't modify[ 3b]#
        #add your code here

        return #end function

#[win]end your code
