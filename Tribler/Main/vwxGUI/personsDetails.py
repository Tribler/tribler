# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from bgPanel import ImagePanel
from TextButton import *
from TasteHeart import *
from tribler_topButton import *
from tribler_List import *
from btn_DetailsHeader import *
#[inc]add your include files here

#[inc]end your include

class personsDetails(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,620),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.SetForegroundColour(wx.Colour(216,216,191))
        self.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_left = bgPanel(self, -1, wx.Point(0,0), wx.Size(10,21))
        self.titlePanel = wx.Panel(self,-1,wx.Point(13,525),wx.Size(280,21))
        self.titlePanel.SetForegroundColour(wx.Colour(255,255,255))
        self.titlePanel.SetBackgroundColour(wx.Colour(0,0,0))
        self.titlePanel.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtitlePanel_VwXEvOnEraseBackground)
        self.titleField = wx.StaticText(self.titlePanel,-1,"",wx.Point(0,5),wx.Size(280,16),wx.ST_NO_AUTORESIZE)
        self.titleField.SetLabel("Title\r\n")
        self.titleField.SetForegroundColour(wx.Colour(255,255,255))
        self.titleField.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(288,0), wx.Size(10,21))
        self.pn240c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(20,86))
        self.pn240c.SetBackgroundColour(wx.Colour(0,0,0))
        self.thumbField = ImagePanel(self.pn240c,-1,wxDefaultPosition,wxDefaultSize)
        self.thumbField.SetDimensions(10,3,80,80)
        self.tabs = wx.Panel(self,-1,wx.Point(0,211),wx.Size(300,18))
        self.tabs.SetBackgroundColour(wx.Colour(0,0,0))
        self.info_detailsTab = TextButton(self.tabs,-1,wxDefaultPosition,wxDefaultSize)
        self.info_detailsTab.SetDimensions(10,0,75,18)
        self.info_detailsTab.SetForegroundColour(wx.Colour(0,0,0))
        self.advanced_detailsTab = TextButton(self.tabs,-1,wxDefaultPosition,wxDefaultSize)
        self.advanced_detailsTab.SetDimensions(95,0,95,16)
        self.advanced_detailsTab.SetForegroundColour(wx.Colour(0,0,0))
        self.detailsC = wx.Panel(self,-1,wx.Point(0,125),wx.Size(298,238))
        self.detailsC.SetBackgroundColour(wx.Colour(255,255,255))
        self.disc_filesText = wx.StaticText(self.detailsC,-1,"",wx.Point(8,7),wx.Size(110,18),wx.ST_NO_AUTORESIZE)
        self.disc_filesText.SetLabel("discovered files:")
        self.disc_filesText.SetForegroundColour(wx.Colour(0,0,0))
        self.discFilesField = wx.StaticText(self.detailsC,-1,"",wx.Point(118,7),wx.Size(111,18),wx.ST_NO_AUTORESIZE)
        self.discFilesField.SetLabel("unknown")
        self.discFilesField.SetForegroundColour(wx.Colour(0,0,0))
        self.disc_personsText = wx.StaticText(self.detailsC,-1,"",wx.Point(8,25),wx.Size(110,18),wx.ST_NO_AUTORESIZE)
        self.disc_personsText.SetLabel("discovered persons:")
        self.disc_personsText.SetForegroundColour(wx.Colour(0,0,0))
        self.discPersonsField = wx.StaticText(self.detailsC,-1,"",wx.Point(118,25),wx.Size(111,18),wx.ST_NO_AUTORESIZE)
        self.discPersonsField.SetLabel("unknown")
        self.discPersonsField.SetForegroundColour(wx.Colour(0,0,0))
        self.recommendationText = wx.StaticText(self.detailsC,-1,"",wx.Point(8,43),wx.Size(110,18),wx.ST_NO_AUTORESIZE)
        self.recommendationText.SetLabel("similar taste:")
        self.recommendationText.SetForegroundColour(wx.Colour(0,0,0))
        self.TasteHeart = TasteHeart(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.TasteHeart.SetDimensions(121,43,14,14)
        self.recommendationField = wx.StaticText(self.detailsC,-1,"",wx.Point(138,43),wx.Size(86,18),wx.ST_NO_AUTORESIZE)
        self.recommendationField.SetLabel("unknown")
        self.recommendationField.SetForegroundColour(wx.Colour(0,0,0))
        self.statusText = wx.StaticText(self.detailsC,-1,"",wx.Point(8,61),wx.Size(110,18),wx.ST_NO_AUTORESIZE)
        self.statusText.SetLabel("status:")
        self.statusText.SetForegroundColour(wx.Colour(0,0,0))
        self.statusField = wx.StaticText(self.detailsC,-1,"",wx.Point(118,61),wx.Size(111,18),wx.ST_NO_AUTORESIZE)
        self.statusField.SetLabel("unknown")
        self.statusField.SetForegroundColour(wx.Colour(0,0,0))
        self.addAsFriend = tribler_topButton(self.detailsC, -1, wx.Point(238,3), wx.Size(55,55))
        self.pn263c = wx.Panel(self.detailsC,-1,wx.Point(0,61),wx.Size(20,15))
        self.pn263c.SetBackgroundColour(wx.Colour(203,203,203))
        self.commonFiles = wx.StaticText(self.pn263c,-1,"",wx.Point(0,0),wx.Size(241,15),wx.ST_NO_AUTORESIZE)
        self.commonFiles.SetLabel("   Common files")
        self.commonFiles.SetForegroundColour(wx.Colour(0,0,0))
        self.commonFiles.SetBackgroundColour(wx.Colour(203,203,203))
        self.commonFilesField = tribler_List(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.commonFilesField.SetDimensions(6,103,284,85)
        self.commonFilesField.SetForegroundColour(wx.Colour(0,0,0))
        self.Peop = btn_DetailsHeader(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.Peop.SetDimensions(0,194,20,15)
        self.alsoDownloaded = wx.StaticText(self.Peop,-1,"",wx.Point(10,0),wx.Size(204,15),wx.ST_NO_AUTORESIZE)
        self.alsoDownloaded.SetLabel("Also downloaded")
        self.alsoDownloaded.SetForegroundColour(wx.Colour(0,0,0))
        self.alsoDownloaded.SetBackgroundColour(wx.Colour(203,203,203))
        self.alsoDownloadedField = DLFilesList(self.detailsC,-1,wxDefaultPosition,wxDefaultSize)
        self.alsoDownloadedField.SetDimensions(6,215,284,160)
        self.alsoDownloadedField.SetForegroundColour(wx.Colour(0,0,0))
        self.white_bottom = bgPanel(self, -1, wx.Point(0,543), wx.Size(300,5))
        self.options = tribler_topButton(self, -1, wx.Point(3,24), wx.Size(62,16))
        self.options.SetForegroundColour(wx.Colour(0,0,0))
        self.options.SetBackgroundColour(wx.Colour(255,255,255))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.headerC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz277s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz226s = wx.BoxSizer(wx.HORIZONTAL)
        self.tabsCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz237s = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.recommendationSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.statusSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz241s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz264sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz267s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz238sC = wx.BoxSizer(wx.VERTICAL)
        self.disc_filesSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.disc_personsSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.headerC,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3s.Add(self.sz277s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn240c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.tabs,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.detailsC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.headerC.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.headerC.Add(self.titlePanel,1,wx.FIXED_MINSIZE,3)
        self.headerC.SetItemMinSize(self.titlePanel,20,10)
        self.headerC.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz277s.Add(self.options,0,wx.FIXED_MINSIZE,3)
        self.sz277s.Add([18,16],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz226s.Add(self.titleField,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.tabsCCCC.Add(self.info_detailsTab,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.tabsCCCC.Add(self.advanced_detailsTab,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add(self.sz237s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.pn263c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.commonFilesField,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.vert_sz184s.Add(self.Peop,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add(self.alsoDownloadedField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz237s.Add(self.vert_sz238sC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz237s.Add(self.downloadSizer,1,wx.FIXED_MINSIZE,4)
        self.downloadSizer.Add([1,55],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add(self.addAsFriend,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.recommendationText,0,wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.TasteHeart,0,wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.recommendationField,0,wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.statusSizer.Add(self.statusText,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.statusSizer.Add(self.statusField,1,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.sz241s.Add([10,84],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz241s.Add(self.thumbField,0,wx.TOP|wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz264sC.Add(self.commonFiles,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz267s.Add(self.alsoDownloaded,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz238sC.Add(self.disc_filesSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238sC.Add(self.disc_personsSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238sC.Add(self.recommendationSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238sC.Add(self.statusSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.disc_filesSizer.Add(self.disc_filesText,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.disc_filesSizer.Add(self.discFilesField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.disc_personsSizer.Add(self.disc_personsText,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.disc_personsSizer.Add(self.discPersonsField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.titlePanel.SetSizer(self.sz226s);self.titlePanel.SetAutoLayout(1);self.titlePanel.Layout();
        self.tabs.SetSizer(self.tabsCCCC);self.tabs.SetAutoLayout(1);self.tabs.Layout();
        self.detailsC.SetSizer(self.vert_sz184s);self.detailsC.SetAutoLayout(1);self.detailsC.Layout();
        self.pn240c.SetSizer(self.sz241s);self.pn240c.SetAutoLayout(1);self.pn240c.Layout();
        self.pn263c.SetSizer(self.sz264sC);self.pn263c.SetAutoLayout(1);self.pn263c.Layout();
        self.Peop.SetSizer(self.sz267s);self.Peop.SetAutoLayout(1);self.Peop.Layout();
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
        #[561]Code event VwX...Don't modify[561]#
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
        #[560]Code VwX...Don't modify[560]#
        #add your code here

        return #end function

#[win]end your code
