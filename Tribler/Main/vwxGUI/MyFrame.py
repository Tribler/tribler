# -*- coding: iso-8859-1 -*-
# Don't modify comment 

import wx
from bgPanel import *
from tribler_topButton import *
from tribler_topButton import SwitchButton
from TextButton import *
from LeftMenu import *
from filterStandard import filterStandard
from standardOverview import *
from playerDockedPanel import *
from standardDetails import *
[ID_MENU_444,ID_MENU_446] = 444,446
#[inc]add your include files here

#[inc]end your include

class MyFrame(wx.Frame):
    def __init__(self,parent,id = -1,title='',pos = wx.Point(1,1),size = wx.Size(952,757),style = wx.DEFAULT_FRAME_STYLE,name = 'frame'):
        pre=wx.PreFrame()
        self.OnPreCreate()
        pre.Create(parent,id,title,pos,size,wx.DEFAULT_FRAME_STYLE,name)
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
        self.pageTitlePanelImg0=self.fileImgBuf[0];
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(212,208,200))
        self.fdfs= wx.MenuBar()
        self.menu443 = wx.Menu()
        self.fdfs.Append(self.menu443,"File")
        itemmenu = wx.MenuItem(self.menu443,ID_MENU_444,"Exit","",wx.ITEM_NORMAL)
        self.menu443.AppendItem(itemmenu)
        self.menu445 = wx.Menu()
        self.fdfs.Append(self.menu445,"Options")
        itemmenu = wx.MenuItem(self.menu445,ID_MENU_446,"Options","",wx.ITEM_NORMAL)
        self.menu445.AppendItem(itemmenu)
        self.SetMenuBar(self.fdfs)
        self.level0 = wx.ScrolledWindow(self,-1,wx.Point(0,0),wx.Size(990,683),wx.VSCROLL|wx.HSCROLL|wx.CLIP_CHILDREN)
        self.level0.SetBackgroundColour(wx.Colour(102,102,102))
        self.topBG = bgPanel(self.level0, -1, wx.Point(0,0), wx.Size(972,90))
        self.searchField = wx.TextCtrl(self.topBG,-1,"",wx.Point(175,32),wx.Size(260,22),wx.TE_PROCESS_ENTER)
        self.searchField.SetLabel("search a file")
        self.searchField.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.search = tribler_topButton(self.topBG, -1, wx.Point(435,11), wx.Size(46,43))
        self.familyFilterText = tribler_topButton(self.topBG, -1, wx.Point(799,7), wx.Size(62,16))
        self.familyFilterOn = SwitchButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.familyFilterOn.SetDimensions(870,3,29,22)
        self.familyFilterOff = SwitchButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.familyFilterOff.SetDimensions(915,3,29,22)
        self.firewallStatus = SwitchButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.firewallStatus.SetDimensions(957,3,20,20)
        self.backButton = tribler_topButton(self.topBG, -1, wx.Point(7,67), wx.Size(47,17))
        self.viewThumbs = SwitchButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.viewThumbs.SetDimensions(593,73,30,14)
        self.viewList = SwitchButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.viewList.SetDimensions(370,70,30,14)
        self.messageField = TextButton(self.topBG,-1,wxDefaultPosition,wxDefaultSize)
        self.messageField.SetDimensions(686,70,285,20)
        self.messageField.Show(False)
        self.hline = bgPanel(self.level0, -1, wx.Point(0,10), wx.Size(20,3))
        self.leftMenuHeader = wx.Panel(self.level0,-1,wx.Point(0,93),wx.Size(20,18))
        self.leftMenuHeader.SetBackgroundColour(wx.Colour(0,0,0))
        self.hideLeft = SwitchButton(self.leftMenuHeader,-1,wxDefaultPosition,wxDefaultSize)
        self.hideLeft.SetDimensions(1,1,18,18)
        self.line2 = bgPanel(self.leftMenuHeader, -1, wx.Point(1,1), wx.Size(3,2))
        self.LeftMenu = LeftMenu(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.LeftMenu.SetDimensions(0,111,180,545)
        self.line = bgPanel(self.level0, -1, wx.Point(223,104), wx.Size(3,339))
        self.pageTitlePanel = wx.Panel(self.level0,-1,wx.Point(172,93),wx.Size(306,26))
        self.pageTitlePanel.SetForegroundColour(wx.Colour(255,255,255))
        self.pageTitlePanel.SetBackgroundColour(wx.Colour(0,0,0))
        self.pageTitlePanel.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpageTitlePanel_VwXEvOnEraseBackground)
        self.pageTitle = wx.StaticText(self.pageTitlePanel,-1,"",wx.Point(10,10),wx.Size(301,15),wx.ST_NO_AUTORESIZE)
        self.pageTitle.SetLabel("--")
        self.pageTitle.SetForegroundColour(wx.Colour(255,255,255))
        self.pageTitle.SetBackgroundColour(wx.Colour(0,0,0))
        self.filterStandard = filterStandard(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.filterStandard.SetDimensions(172,119,523,70)
        self.filterStandard.SetBackgroundColour(wx.Colour(51,51,51))
        self.advancedFiltering = tribler_topButton(self.level0, -1, wx.Point(591,189), wx.Size(103,15))
        self.standardOverview = standardOverview(self.level0,-1,wx.Point(230,224),wx.Size(322,559))
        self.standardOverview.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.rightMenuHeader = wx.Panel(self.level0,-1,wx.Point(743,93),wx.Size(20,18))
        self.rightMenuHeader.SetBackgroundColour(wx.Colour(0,0,0))
        self.line3 = bgPanel(self.rightMenuHeader, -1, wx.Point(1,1), wx.Size(3,9))
        self.hideRight = SwitchButton(self.rightMenuHeader,-1,wxDefaultPosition,wxDefaultSize)
        self.hideRight.SetDimensions(3,0,18,18)
        self.line4 = bgPanel(self.level0, -1, wx.Point(765,-797), wx.Size(3,9))
        self.playerDockedPanel = playerDockedPanel(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.playerDockedPanel.SetDimensions(746,111,260,160)
        self.standardDetails = standardDetails(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.standardDetails.SetDimensions(709,172,260,326)
        self.vertical_1 = wx.BoxSizer(wx.VERTICAL)
        self.horizontal_2 = wx.BoxSizer(wx.HORIZONTAL)
        self.menuLeft = wx.BoxSizer(wx.VERTICAL)
        self.sz564s = wx.BoxSizer(wx.HORIZONTAL)
        self.standardOverviewSizer = wx.BoxSizer(wx.VERTICAL)
        self.sz548s = wx.BoxSizer(wx.HORIZONTAL)
        self.rightSide = wx.BoxSizer(wx.VERTICAL)
        self.sz572s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz350sCCC = wx.BoxSizer(wx.VERTICAL)
        self.sz482sC = wx.BoxSizer(wx.HORIZONTAL)
        self.horCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz311sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz29sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz574s = wx.BoxSizer(wx.VERTICAL)
        self.sz576s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz576sC = wx.BoxSizer(wx.HORIZONTAL)
        self.vertical_1.Add(self.topBG,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical_1.Add(self.hline,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vertical_1.Add(self.horizontal_2,1,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.horizontal_2.Add(self.menuLeft,0,wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.horizontal_2.Add(self.standardOverviewSizer,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.horizontal_2.Add(self.rightSide,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.menuLeft.Add(self.leftMenuHeader,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.menuLeft.Add(self.sz564s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz564s.Add(self.LeftMenu,1,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz564s.Add(self.line,0,wx.EXPAND|wx.ALIGN_RIGHT|wx.FIXED_MINSIZE,3)
        self.standardOverviewSizer.Add(self.pageTitlePanel,0,wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.standardOverviewSizer.SetItemMinSize(self.pageTitlePanel,20,10)
        self.standardOverviewSizer.Add(self.filterStandard,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.standardOverviewSizer.Add(self.sz548s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.standardOverviewSizer.Add(self.standardOverview,1,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,10)
        self.standardOverviewSizer.SetItemMinSize(self.standardOverview,603,10)
        self.sz548s.Add([408,5],1,wx.FIXED_MINSIZE,3)
        self.sz548s.Add(self.advancedFiltering,0,wx.RIGHT|wx.FIXED_MINSIZE,12)
        self.rightSide.Add(self.rightMenuHeader,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.rightSide.Add(self.sz572s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz572s.Add(self.line4,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz572s.Add(self.sz574s,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz350sCCC.Add(self.sz482sC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz350sCCC.Add(self.horCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz482sC.Add([175,67],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz482sC.Add(self.searchField,0,wx.TOP|wx.FIXED_MINSIZE,21)
        self.sz482sC.Add(self.search,0,wx.TOP|wx.FIXED_MINSIZE,11)
        self.sz482sC.Add([208,9],1,wx.FIXED_MINSIZE,3)
        self.sz482sC.Add(self.sz311sCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz482sC.Add(self.firewallStatus,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz482sC.Add([10,9],0,wx.FIXED_MINSIZE,3)
        self.horCC.Add([7,20],0,wx.FIXED_MINSIZE,3)
        self.horCC.Add(self.backButton,0,wx.FIXED_MINSIZE,3)
        self.horCC.Add([283,5],1,wx.FIXED_MINSIZE,3)
        self.horCC.Add(self.viewThumbs,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,3)
        self.horCC.Add(self.viewList,0,wx.TOP|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.horCC.Add([283,5],0,wx.FIXED_MINSIZE,3)
        self.horCC.Add(self.messageField,0,wx.TOP|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz311sCC.Add([105,28],1,wx.FIXED_MINSIZE,3)
        self.sz311sCC.Add(self.familyFilterText,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,7)
        self.sz311sCC.Add(self.familyFilterOn,0,wx.TOP|wx.FIXED_MINSIZE,3)
        self.sz311sCC.Add(self.familyFilterOff,0,wx.TOP|wx.FIXED_MINSIZE,3)
        self.sz311sCC.Add([10,18],0,wx.FIXED_MINSIZE,3)
        self.sz29sC.Add([15,24],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz29sC.Add(self.pageTitle,1,wx.TOP|wx.FIXED_MINSIZE,7)
        self.sz574s.Add(self.playerDockedPanel,0,wx.RIGHT|wx.FIXED_MINSIZE,5)
        self.sz574s.Add(self.standardDetails,1,wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,5)
        self.sz576s.Add([160,16],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz576s.Add(self.hideLeft,0,wx.FIXED_MINSIZE,3)
        self.sz576s.Add(self.line2,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz576sC.Add(self.line3,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz576sC.Add(self.hideRight,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz576sC.Add([245,16],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.level0.SetSizer(self.vertical_1);self.level0.SetAutoLayout(1);self.level0.Layout();
        self.topBG.SetSizer(self.sz350sCCC);self.topBG.SetAutoLayout(1);self.topBG.Layout();
        self.pageTitlePanel.SetSizer(self.sz29sC);self.pageTitlePanel.SetAutoLayout(1);self.pageTitlePanel.Layout();
        self.leftMenuHeader.SetSizer(self.sz576s);self.leftMenuHeader.SetAutoLayout(1);self.leftMenuHeader.Layout();
        self.rightMenuHeader.SetSizer(self.sz576sC);self.rightMenuHeader.SetAutoLayout(1);self.rightMenuHeader.Layout();
        self.Refresh()
        self.level0.SetScrollbars(1,1,1,1)
        self.level0.FitInside()
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
    def VwXpageTitlePanel_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pageTitlePanel,self.pageTitlePanelImg0,2)
        self.pageTitlePanel_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def pageTitlePanel_VwXEvOnEraseBackground(self,event): #init function
        #[5d7]Code event VwX...Don't modify[5d7]#
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
        #[338]Code VwX...Don't modify[338]#
        #add your code here

        return #end function

#[win]end your code
