# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class messageItem(wx.Panel):
    def __init__(self,parent,id = -1, pos = wx.Point(0,0), size = wx.Size(625,35), style = wx.TAB_TRAVERSAL, name = "panel"):
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
        self.fileImgBuf[0] = wx.Bitmap("images/6.jpg",wx.BITMAP_TYPE_JPEG)
        self.fileImgBuf[1] = wx.Bitmap("images/1p_32x32.gif",wx.BITMAP_TYPE_GIF)
        self.bm4cCImg0=self.fileImgBuf[0];
        self.bm4cImg0=self.fileImgBuf[1];
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.bm4cC = wx.StaticBitmap(self,-1,self.bm4cCImg0,wx.Point(3,0),wx.Size(35,35),wx.SIMPLE_BORDER)
        self.bm4cC.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.bm4c = wx.StaticBitmap(self,-1,self.bm4cImg0,wx.Point(58,1),wx.Size(32,32),wx.SIMPLE_BORDER)
        self.bm4c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.st5cC = wx.StaticText(self,-1,"",wx.Point(96,9),wx.Size(77,17),wx.ST_NO_AUTORESIZE)
        self.st5cC.SetLabel("Sanne")
        self.st5cC.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.st5cC.SetForegroundColour(wx.Colour(0,0,0))
        self.st5cCC = wx.StaticText(self,-1,"",wx.Point(317,0),wx.Size(207,35),wx.ST_NO_AUTORESIZE)
        self.st5cCC.SetLabel("you really should see this. The place where we had coffee...")
        self.st5cCC.SetFont(wx.Font(9,74,90,90,0,"Verdana"))
        self.st5cCC.SetForegroundColour(wx.Colour(0,0,0))
        self.klk = wx.StaticText(self,-1,"",wx.Point(153,9),wx.Size(137,17))
        self.klk.SetLabel("A San Francisco Minute")
        self.klk.SetFont(wx.Font(10,74,90,90,0,"Verdana"))
        self.klk.SetForegroundColour(wx.Colour(0,0,0))
        self.sz3s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.bm4cC,0,wx.LEFT|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.bm4c,0,wx.LEFT|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cC,0,wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.klk,0,wx.RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,7)
        self.sz3s.Add(self.st5cCC,0,wx.RIGHT|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,12)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.Refresh()
        return
    def VwXDelComp(self):
        return

#[win]add your code here

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
        #[1e1]Code VwX...Don't modify[1e1]#
        #add your code here

        return #end function

#[win]end your code
