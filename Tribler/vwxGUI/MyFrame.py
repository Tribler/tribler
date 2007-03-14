# -*- coding: iso-8859-1 -*-
# Don't modify comment 

import wx
from bgPanel import *
from tribler_topButton import *
from standardOverview import *
from standardDetails import *
from standardStatus import *
[ID_MENU_444,ID_MENU_446] = 444,446
#[inc]add your include files here

#[inc]end your include

class MyFrame(wx.Frame):
    def __init__(self,parent,id = -1,title='',pos = wx.Point(1,1),size = wx.Size(1024,768),style = wx.DEFAULT_FRAME_STYLE,name = 'frame'):
        pre=wx.PreFrame()
        self.OnPreCreate()
        pre.Create(parent,id,title,pos,size,style,name)
        self.PostCreate(pre)
        self.initBefore()
        self.VwXinit()
        self.initAfter()

    def __del__(self):
        self.Ddel()
        return


    def VwXinit(self):
        self.fileImgBuf=[None] * 9
        self.fileImgBuf[0] = wx.Bitmap("images/topbg1.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/tribler_topbutton0.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/tribler_topbutton1.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/tribler_topbutton2.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[4] = wx.Bitmap("images/tribler_topbutton3.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[5] = wx.Bitmap("images/topbg2.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[6] = wx.Bitmap("images/topbg3.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[7] = wx.Bitmap("images/tribler_topbutton4.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[8] = wx.Bitmap("images/tribler_topbutton5.png",wx.BITMAP_TYPE_PNG)
        self.topbg1Img0=self.fileImgBuf[0];
        self.tribler_topButton0Img0=self.fileImgBuf[1];
        self.tribler_topButton1Img0=self.fileImgBuf[2];
        self.tribler_topButton2Img0=self.fileImgBuf[3];
        self.tribler_topButton3Img0=self.fileImgBuf[4];
        self.topbg2Img0=self.fileImgBuf[5];
        self.topbg3Img0=self.fileImgBuf[6];
        self.tribler_topButton4Img0=self.fileImgBuf[7];
        self.tribler_topButton5Img0=self.fileImgBuf[8];
        self.SetToolTipString('d')
        self.Show(False)
        self.SetBackgroundColour(wx.Colour(212,208,200))
        self.fdfs= wx.MenuBar()
        self.menu443 = wx.Menu()
        self.fdfs.Append(self.menu443,"File")
        itemmenu = wx.MenuItem(self.menu443,ID_MENU_444,"Exit","",0)
        self.menu443.AppendItem(itemmenu)
        self.menu445 = wx.Menu()
        self.fdfs.Append(self.menu445,"Options")
        itemmenu = wx.MenuItem(self.menu445,ID_MENU_446,"Options","",0)
        self.menu445.AppendItem(itemmenu)
        self.SetMenuBar(self.fdfs)
        self.level0 = wx.ScrolledWindow(self,-1,wx.Point(0,0),wx.Size(1024,768),wx.VSCROLL|wx.HSCROLL|wx.CLIP_CHILDREN)
        self.level0.SetBackgroundColour(wx.Colour(102,102,102))
        self.topbg1 = bgPanel(self.level0, -1, wx.Point(0,0), wx.Size(614,89))
        self.topbg1.SetBackgroundColour(wx.Colour(0,0,0))
        self.topbg1.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtopbg1_VwXEvOnEraseBackground)
        self.tribler_topButton0 = tribler_topButton(self.topbg1, -1, wx.Point(29,5), wx.Size(60,72))
        # bla bla
        
        #fdsfdsf

        self.tribler_topButton0.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton0_VwXEvOnEraseBackground)
        self.tribler_topButton1 = tribler_topButton(self.topbg1, -1, wx.Point(89,5), wx.Size(60,72))
        self.tribler_topButton1.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton1_VwXEvOnEraseBackground)
        self.tribler_topButton2 = tribler_topButton(self.topbg1, -1, wx.Point(173,5), wx.Size(60,72))
        self.tribler_topButton2.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton2_VwXEvOnEraseBackground)
        self.tribler_topButton3 = tribler_topButton(self.topbg1, -1, wx.Point(251,5), wx.Size(60,72))
        self.tribler_topButton3.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton3_VwXEvOnEraseBackground)
        self.topbg2 = bgPanel(self.level0, -1, wx.Point(614,0), wx.Size(21,89))
        self.topbg2.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtopbg2_VwXEvOnEraseBackground)
        self.topbg3 = bgPanel(self.level0, -1, wx.Point(803,0), wx.Size(269,89))
        self.topbg3.SetBackgroundColour(wx.Colour(0,0,0))
        self.topbg3.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtopbg3_VwXEvOnEraseBackground)
        self.st176cCC = wx.StaticText(self.topbg3,-1,"",wx.Point(89,10),wx.Size(119,13),wx.ST_NO_AUTORESIZE)
        self.st176cCC.SetLabel("downloading:")
        self.st176cCC.SetForegroundColour(wx.Colour(255,255,255))
        self.st177cCC = wx.StaticText(self.topbg3,-1,"",wx.Point(89,29),wx.Size(124,13),wx.ST_NO_AUTORESIZE)
        self.st177cCC.SetLabel("uploading:")
        self.st177cCC.SetForegroundColour(wx.Colour(255,255,255))
        self.st178cCC = wx.StaticText(self.topbg3,-1,"",wx.Point(89,43),wx.Size(119,13),wx.ST_NO_AUTORESIZE)
        self.st178cCC.SetLabel("discovered content:")
        self.st178cCC.SetForegroundColour(wx.Colour(255,255,255))
        self.st179cCC = wx.StaticText(self.topbg3,-1,"",wx.Point(89,57),wx.Size(114,13),wx.ST_NO_AUTORESIZE)
        self.st179cCC.SetLabel("discovered peers:")
        self.st179cCC.SetForegroundColour(wx.Colour(255,255,255))
        self.tribler_topButton4 = tribler_topButton(self.topbg1, -1, wx.Point(311,5), wx.Size(60,72))
        self.tribler_topButton4.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton4_VwXEvOnEraseBackground)
        self.tribler_topButton5 = tribler_topButton(self.topbg1, -1, wx.Point(371,5), wx.Size(60,72))
        self.tribler_topButton5.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXtribler_topButton5_VwXEvOnEraseBackground)
        self.backButton = tribler_topButton(self.topbg1, -1, wx.Point(0,59), wx.Size(25,29))
        self.standardOverview = standardOverview(self.level0,-1,wx.Point(9,98),wx.Size(515,540))
        self.standardDetails = standardDetails(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.standardDetails.SetDimensions(715,98,300,462)
        self.standardStatus = standardStatus(self.level0,-1,wxDefaultPosition,wxDefaultSize)
        self.standardStatus.SetDimensions(715,569,300,75)
        self.sz102sC = wx.BoxSizer(wx.VERTICAL)
        self.sizerTopMenu = wx.BoxSizer(wx.HORIZONTAL)
        self.sz11sCCCCCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz135s = wx.BoxSizer(wx.VERTICAL)
        self.sz164sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz213s = wx.BoxSizer(wx.VERTICAL)
        self.sz180sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz175sCC = wx.BoxSizer(wx.VERTICAL)
        self.setMinHeight = wx.BoxSizer(wx.VERTICAL)
        self.setMinWidth = wx.BoxSizer(wx.HORIZONTAL)
        self.sz102sC.Add(self.sizerTopMenu,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz102sC.Add(self.sz11sCCCCCC,1,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sizerTopMenu.Add(self.topbg1,0,wx.FIXED_MINSIZE,3)
        self.sizerTopMenu.Add(self.topbg2,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sizerTopMenu.Add(self.topbg3,0,wx.FIXED_MINSIZE,3)
        self.sz11sCCCCCC.Add(self.standardOverview,1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz11sCCCCCC.Add(self.sz135s,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz135s.Add(self.standardDetails,0,wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz135s.Add(self.standardStatus,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz164sC.Add(self.sz213s,0,wx.FIXED_MINSIZE,3)
        self.sz164sC.Add(self.tribler_topButton0,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz164sC.Add(self.tribler_topButton1,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz164sC.Add([36,72],0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz164sC.Add(self.tribler_topButton2,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz164sC.Add(self.tribler_topButton3,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz164sC.Add(self.tribler_topButton4,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz164sC.Add(self.tribler_topButton5,0,wx.TOP|wx.BOTTOM|wx.FIXED_MINSIZE,5)
        self.sz213s.Add([29,59],0,wx.FIXED_MINSIZE,3)
        self.sz213s.Add(self.backButton,0,wx.FIXED_MINSIZE,3)
        self.sz180sC.Add([80,83],0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz180sC.Add(self.sz175sCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz180sC.Add(self.setMinHeight,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz175sCC.Add(self.setMinWidth,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz175sCC.Add(self.st176cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,7)
        self.sz175sCC.Add(self.st177cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz175sCC.Add(self.st178cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.sz175sCC.Add(self.st179cCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
        self.setMinHeight.Add([2,89],0,wx.FIXED_MINSIZE,3)
        self.setMinWidth.Add([187,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.level0.SetSizer(self.sz102sC);self.level0.SetAutoLayout(1);self.level0.Layout();
        self.topbg1.SetSizer(self.sz164sC);self.topbg1.SetAutoLayout(1);self.topbg1.Layout();
        self.topbg3.SetSizer(self.sz180sC);self.topbg3.SetAutoLayout(1);self.topbg3.Layout();
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
    def VwXtopbg1_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.topbg1,self.topbg1Img0,0)
        self.topbg1_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton0_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton0,self.tribler_topButton0Img0,0)
        self.tribler_topButton0_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton1_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton1,self.tribler_topButton1Img0,0)
        self.tribler_topButton1_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton2_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton2,self.tribler_topButton2Img0,0)
        self.tribler_topButton2_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton3_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton3,self.tribler_topButton3Img0,0)
        self.tribler_topButton3_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtopbg2_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.topbg2,self.topbg2Img0,2)
        self.topbg2_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtopbg3_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.topbg3,self.topbg3Img0,2)
        self.topbg3_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton4_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton4,self.tribler_topButton4Img0,0)
        self.tribler_topButton4_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXtribler_topButton5_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.tribler_topButton5,self.tribler_topButton5Img0,0)
        self.tribler_topButton5_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def tribler_topButton5_VwXEvOnEraseBackground(self,event): #init function
        #[5b3]Code event VwX...Don't modify[5b3]#
        #add your code here
        event.Skip()

        return #end function

    def tribler_topButton4_VwXEvOnEraseBackground(self,event): #init function
        #[5b2]Code event VwX...Don't modify[5b2]#
        #add your code here
        event.Skip()

        return #end function



    def topbg2_VwXEvOnEraseBackground(self,event): #init function
        #[16b]Code event VwX...Don't modify[16b]#
        #add your code here
        event.Skip()

        return #end function





    def topbg3_VwXEvOnEraseBackground(self,event): #init function
        #[ 58]Code event VwX...Don't modify[ 58]#
        #add your code here
        event.Skip()

        return #end function

    def topbg1_VwXEvOnEraseBackground(self,event): #init function
        #[ 53]Code event VwX...Don't modify[ 53]#
        #add your code here
        event.Skip()

        return #end function


    def tribler_topButton1_VwXEvOnEraseBackground(self,event): #init function
        #[61b]Code event VwX...Don't modify[61b]#
        #add your code here
        event.Skip()

        return #end function


    def tribler_topButton3_VwXEvOnEraseBackground(self,event): #init function
        #[141]Code event VwX...Don't modify[141]#
        #add your code here
        event.Skip()

        return #end function

    def tribler_topButton2_VwXEvOnEraseBackground(self,event): #init function
        #[140]Code event VwX...Don't modify[140]#
        #add your code here
        event.Skip()

        return #end function

    def tribler_topButton0_VwXEvOnEraseBackground(self,event): #init function
        #[13f]Code event VwX...Don't modify[13f]#
        #add your code here
        event.Skip()

        return #end function


            




    def jelle(self, i):
        print i
        
    def OnPreCreate(self):
        #add your code here
        self.utility = None
        self.jelle(0)
        return

    def initBefore(self):
        #add your code here

        return

    def initAfter(self):
        #add your code here
        self.Centre() 
        self.Show()
        return

    def Ddel(self): #init function
        #[ f9]Code VwX...Don't modify[ f9]#
        #add your code here

        return #end function

#[win]end your code
