# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class libraryItem(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(625,35),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf[1] = wx.Bitmap("images/contentrating.png",wx.BITMAP_TYPE_PNG)
        self.bm4cImg0=self.fileImgBuf[0];
        self.bm15cImg0=self.fileImgBuf[1];
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.bm4c = wx.StaticBitmap(self,-1,self.bm4cImg0,wx.Point(3,3),wx.Size(55,35),wx.SIMPLE_BORDER)
        self.bm4c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.st5c = wx.StaticText(self,-1,"",wx.Point(58,3),wx.Size(162,14),wx.ST_NO_AUTORESIZE)
        self.st5c.SetLabel("NOS 8 Uur Journaal van...")
        self.st5c.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.st13c = wx.StaticText(self,-1,"",wx.Point(61,20),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st13c.SetLabel("video (avi) 01m32")
        self.st13c.SetForegroundColour(wx.Colour(128,128,128))
        self.bm15c = wx.StaticBitmap(self,-1,self.bm15cImg0,wx.Point(226,3),wx.Size(77,17))
        self.st5cCC = wx.StaticText(self,-1,"",wx.Point(306,13),wx.Size(87,15),wx.ST_NO_AUTORESIZE)
        self.st5cCC.SetLabel("progress pic")
        self.st5cCC.SetForegroundColour(wx.Colour(255,85,0))
        self.ck17c = wx.CheckBox(self,-1,"",wx.Point(396,3),wx.Size(13,13))
        self.st5cC = wx.StaticText(self,-1,"",wx.Point(409,3),wx.Size(77,15),wx.ST_NO_AUTORESIZE)
        self.st5cC.SetLabel("archive")
        self.st5cC.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCCC = wx.StaticText(self,-1,"",wx.Point(535,0),wx.Size(137,13),wx.ST_NO_AUTORESIZE)
        self.st5cCCC.SetLabel("> play")
        self.st5cCCC.SetForegroundColour(wx.Colour(255,85,0))
        self.ck17cC = wx.CheckBox(self,-1,"",wx.Point(393,18),wx.Size(13,13))
        self.st5cCCCCC = wx.StaticText(self,-1,"",wx.Point(412,18),wx.Size(82,18),wx.ST_NO_AUTORESIZE)
        self.st5cCCCCC.SetLabel("private")
        self.st5cCCCCC.SetForegroundColour(wx.Colour(128,128,128))
        self.sz3s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz12s = wx.BoxSizer(wx.VERTICAL)
        self.sz14s = wx.BoxSizer(wx.VERTICAL)
        self.sz16s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz16sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.bm4c,0,wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz12s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.bm15c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cCC,0,wx.TOP|wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz14s,0,wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cCCC,0,wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz12s.Add(self.st5c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz12s.Add(self.st13c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14s.Add(self.sz16s,0,wx.FIXED_MINSIZE,3)
        self.sz14s.Add(self.sz16sC,0,wx.FIXED_MINSIZE,3)
        self.sz16s.Add(self.ck17c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz16s.Add(self.st5cC,0,wx.TOP|wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz16sC.Add(self.ck17cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz16sC.Add(self.st5cCCCCC,0,wx.LEFT|wx.EXPAND|wx.FIXED_MINSIZE,3)
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
        #[1e8]Code VwX...Don't modify[1e8]#
        #add your code here

        return #end function

#[win]end your code
