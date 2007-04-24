# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from bgPanel import *
from TextButton import *
from tribler_topButton import *
from TasteHeart import *
from btn_DetailsHeader import *
#[inc]add your include files here

#[inc]end your include

class libraryDetails(wx.Panel):
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
        self.black_top_left = bgPanel(self, -1, wx.Point(3,3), wx.Size(10,21))
        self.titlePanel = wx.Panel(self,-1,wx.Point(13,3),wx.Size(280,21))
        self.titlePanel.SetForegroundColour(wx.Colour(255,255,255))
        self.titlePanel.SetBackgroundColour(wx.Colour(0,0,0))
        self.titlePanel.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtitlePanel_VwXEvOnEraseBackground)
        self.titleField = wx.StaticText(self.titlePanel,-1,"",wx.Point(3,3),wx.Size(280,18),wx.ST_NO_AUTORESIZE)
        self.titleField.SetLabel("Title\r\n")
        self.titleField.SetForegroundColour(wx.Colour(255,255,255))
        self.titleField.SetBackgroundColour(wx.Colour(0,0,0))
        self.black_top_right = bgPanel(self, -1, wx.Point(275,3), wx.Size(10,21))
        self.thumbField = bgPanel(self, -1, wx.Point(3,24), wx.Size(300,170))
        self.tabs = wx.Panel(self,-1,wx.Point(3,194),wx.Size(300,28))
        self.tabs.SetBackgroundColour(wx.Colour(0,0,0))
        self.info_detailsTab = TextButton(self.tabs,-1,wxDefaultPosition,wxDefaultSize)
        self.info_detailsTab.SetDimensions(3,13,75,18)
        self.files_detailsTab = TextButton(self.tabs,-1,wxDefaultPosition,wxDefaultSize)
        self.files_detailsTab.SetDimensions(88,13,75,18)
        self.details = wx.Panel(self,-1,wx.Point(0,219),wx.Size(300,348))
        self.details.SetBackgroundColour(wx.Colour(255,255,255))
        self.st209cCC = wx.StaticText(self.details,-1,"",wx.Point(8,7),wx.Size(79,18),wx.ST_NO_AUTORESIZE)
        self.st209cCC.SetLabel("size:")
        self.sizeField = wx.StaticText(self.details,-1,"",wx.Point(90,10),wx.Size(131,18),wx.ST_NO_AUTORESIZE)
        self.sizeField.SetLabel("unknown")
        self.st209c = wx.StaticText(self.details,-1,"",wx.Point(11,28),wx.Size(79,18),wx.ST_NO_AUTORESIZE)
        self.st209c.SetLabel("creation date:")
        self.creationdateField = wx.StaticText(self.details,-1,"",wx.Point(90,28),wx.Size(131,18))
        self.creationdateField.SetLabel("unknown")
        self.st209cC = wx.StaticText(self.details,-1,"",wx.Point(11,46),wx.Size(79,18),wx.ST_NO_AUTORESIZE)
        self.st209cC.SetLabel("popularity:")
        self.up = bgPanel(self.details, -1, wx.Point(90,46), wx.Size(11,14))
        self.up.SetBackgroundColour(wx.Colour(255,255,255))
        self.popularityField1 = wx.StaticText(self.details,-1,"",wx.Point(101,46),wx.Size(21,18))
        self.popularityField1.SetLabel("?")
        self.down = bgPanel(self.details, -1, wx.Point(126,46), wx.Size(11,14))
        self.down.SetBackgroundColour(wx.Colour(255,255,255))
        self.popularityField2 = wx.StaticText(self.details,-1,"",wx.Point(157,46),wx.Size(21,18))
        self.popularityField2.SetLabel("?")
        self.refresh = tribler_topButton(self.details, -1, wx.Point(182,46), wx.Size(11,12))
        self.st209cCCC = wx.StaticText(self.details,-1,"",wx.Point(11,64),wx.Size(79,15),wx.ST_NO_AUTORESIZE)
        self.st209cCCC.SetLabel("fit to taste:")
        self.TasteHeart = TasteHeart(self.details,-1,wxDefaultPosition,wxDefaultSize)
        self.TasteHeart.SetDimensions(90,64,14,14)
        self.recommendationField = wx.StaticText(self.details,-1,"",wx.Point(107,64),wx.Size(101,12),wx.ST_NO_AUTORESIZE)
        self.recommendationField.SetLabel("unknown")
        self.Desc = wx.StaticText(self.details,-1,"",wx.Point(0,105),wx.Size(199,15),wx.ST_NO_AUTORESIZE)
        self.Desc.SetLabel("   Description")
        self.Desc.SetBackgroundColour(wx.Colour(203,203,203))
        self.descriptionField = wx.StaticText(self.details,-1,"",wx.Point(3,105),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.descriptionField.SetLabel("no description available")
        self.descriptionField.SetFont(wx.Font(8,74,93,90,0,"Verdana"))
        self.Peop = btn_DetailsHeader(self.details,-1,wxDefaultPosition,wxDefaultSize)
        self.Peop.SetDimensions(3,184,20,20)
        self.st202cC = wx.StaticText(self.Peop,-1,"",wx.Point(10,0),wx.Size(204,14),wx.ST_NO_AUTORESIZE)
        self.st202cC.SetLabel("People who like this also like")
        self.st202cC.SetBackgroundColour(wx.Colour(203,203,203))
        self.peoplewhoField = wx.StaticText(self.details,-1,"",wx.Point(3,204),wx.Size(265,73),wx.ST_NO_AUTORESIZE)
        self.peoplewhoField.SetLabel("no info available")
        self.peoplewhoField.SetFont(wx.Font(8,74,93,90,0,"Verdana"))
        self.white_bottom = bgPanel(self, -1, wx.Point(3,275), wx.Size(300,5))
        self.LibraryOptions = wx.StaticText(self.details,-1,"",wx.Point(0,87),wx.Size(199,15),wx.ST_NO_AUTORESIZE)
        self.LibraryOptions.SetLabel("   Library options")
        self.LibraryOptions.SetBackgroundColour(wx.Colour(203,203,203))
        self.privateField = wx.CheckBox(self.details,-1,"",wx.Point(8,105),wx.Size(155,18))
        self.privateField.SetLabel('private')
        self.privateField.SetForegroundColour(wx.Colour(0,0,0))
        self.archiveField = wx.CheckBox(self.details,-1,"",wx.Point(8,123),wx.Size(160,18))
        self.archiveField.SetLabel('archive')
        self.archiveField.SetForegroundColour(wx.Colour(0,0,0))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.BoxSizer(wx.HORIZONTAL)
        self.sz226s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz259s = wx.BoxSizer(wx.VERTICAL)
        self.tabsCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz184s = wx.BoxSizer(wx.VERTICAL)
        self.sz237s = wx.BoxSizer(wx.HORIZONTAL)
        self.vert_sz238s = wx.BoxSizer(wx.VERTICAL)
        self.sizeSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.creationdateSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.popularitySizer = wx.BoxSizer(wx.HORIZONTAL)
        self.recommendationSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.header,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz3s.Add(self.thumbField,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.tabs,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz3s.Add(self.details,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.white_bottom,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.header.Add(self.black_top_left,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.header.Add(self.titlePanel,1,wx.FIXED_MINSIZE,3)
        self.header.SetItemMinSize(self.titlePanel,20,10)
        self.header.Add(self.black_top_right,0,wx.EXPAND|wx.FIXED_MINSIZE,0)
        self.sz226s.Add(self.titleField,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz259s.Add([296,10],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz259s.Add(self.tabsCCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.tabsCCCC.Add(self.info_detailsTab,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.tabsCCCC.Add(self.files_detailsTab,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add(self.sz237s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.LibraryOptions,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.privateField,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,8)
        self.vert_sz184s.Add(self.archiveField,0,wx.LEFT|wx.FIXED_MINSIZE,8)
        self.vert_sz184s.Add(self.Desc,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert_sz184s.Add(self.descriptionField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.vert_sz184s.Add(self.Peop,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.vert_sz184s.Add(self.peoplewhoField,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz237s.Add(self.vert_sz238s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz237s.Add(self.downloadSizer,1,wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.vert_sz238s.Add(self.sizeSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238s.Add(self.creationdateSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238s.Add(self.popularitySizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.vert_sz238s.Add(self.recommendationSizer,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sizeSizer.Add(self.st209cCC,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sizeSizer.Add(self.sizeField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.creationdateSizer.Add(self.st209c,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.creationdateSizer.Add(self.creationdateField,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.popularitySizer.Add(self.st209cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.popularitySizer.Add(self.up,0,wx.FIXED_MINSIZE,3)
        self.popularitySizer.Add(self.popularityField1,0,wx.LEFT|wx.EXPAND,4)
        self.popularitySizer.Add(self.down,0,wx.LEFT|wx.FIXED_MINSIZE,20)
        self.popularitySizer.Add(self.popularityField2,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.popularitySizer.Add(self.refresh,0,wx.LEFT|wx.FIXED_MINSIZE,25)
        self.recommendationSizer.Add(self.st209cCCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.TasteHeart,0,wx.TOP|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.recommendationSizer.Add(self.recommendationField,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add([69,72],1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.titlePanel.SetSizer(self.sz226s);self.titlePanel.SetAutoLayout(1);self.titlePanel.Layout();
        self.tabs.SetSizer(self.sz259s);self.tabs.SetAutoLayout(1);self.tabs.Layout();
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
        #[6d8]Code event VwX...Don't modify[6d8]#
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
        #[6d7]Code VwX...Don't modify[6d7]#
        #add your code here

        return #end function

#[win]end your code
