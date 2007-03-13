# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class torrentItem(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(125,190),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf=[None] * 4
        self.fileImgBuf[0] = wx.Bitmap("images/6.jpg",wx.BITMAP_TYPE_JPEG)
        self.fileImgBuf[1] = wx.Bitmap("images/up.gif",wx.BITMAP_TYPE_GIF)
        self.fileImgBuf[2] = wx.Bitmap("images/down.gif",wx.BITMAP_TYPE_GIF)
        self.fileImgBuf[3] = wx.Bitmap("images/size.gif",wx.BITMAP_TYPE_GIF)
        self.bm4cImg0=self.fileImgBuf[0];
        self.bm18cImg0=self.fileImgBuf[1];
        self.bm19cImg0=self.fileImgBuf[2];
        self.bm18cCImg0=self.fileImgBuf[3];
        self.Show(True)
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        self.bm4c = wx.StaticBitmap(self,-1,self.bm4cImg0,wx.Point(0,0),wx.Size(125,70),wx.SIMPLE_BORDER)
        self.bm4c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.st5c = wx.StaticText(self,-1,"",wx.Point(0,73),wx.Size(117,38),wx.ST_NO_AUTORESIZE)
        self.st5c.SetLabel("NOS 8 Uur Journaal van 24 jan. 2007 and some other characters")
        self.st5c.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.st5cCCCC = wx.StaticText(self,-1,"",wx.Point(26,120),wx.Size(35,11))
        self.st5cCCCC.SetLabel("130 MB")
        self.st5cCCCC.SetFont(wx.Font(8,74,90,90,0,"Tahoma"))
        self.st5cCCCC.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cC = wx.StaticText(self,-1,"",wx.Point(17,120),wx.Size(18,11),wx.ST_NO_AUTORESIZE)
        self.st5cC.SetLabel("avi")
        self.st5cC.SetForegroundColour(wx.Colour(128,128,128))
        self.bm18c = wx.StaticBitmap(self,-1,self.bm18cImg0,wx.Point(3,135),wx.Size(5,8))
        self.st20c = wx.StaticText(self,-1,"",wx.Point(14,136),wx.Size(19,15),wx.ST_NO_AUTORESIZE)
        self.st20c.SetLabel("40")
        self.st20c.SetForegroundColour(wx.Colour(128,128,128))
        self.bm19c = wx.StaticBitmap(self,-1,self.bm19cImg0,wx.Point(39,135),wx.Size(5,8))
        self.st21c = wx.StaticText(self,-1,"",wx.Point(50,136),wx.Size(19,15),wx.ST_NO_AUTORESIZE)
        self.st21c.SetLabel("10")
        self.st21c.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCCC = wx.StaticText(self,-1,"",wx.Point(0,172),wx.Size(117,13),wx.ST_NO_AUTORESIZE)
        self.st5cCCC.SetLabel("> download")
        self.st5cCCC.SetForegroundColour(wx.Colour(255,85,0))
        self.st5cCC = wx.StaticText(self,-1,"",wx.Point(18,120),wx.Size(8,16),wx.ST_NO_AUTORESIZE)
        self.st5cCC.SetLabel("| ")
        self.st5cCC.SetForegroundColour(wx.Colour(128,128,128))
        self.bm18cC = wx.StaticBitmap(self,-1,self.bm18cCImg0,wx.Point(3,120),wx.Size(11,16))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz17s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz22s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.bm4c,0,wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz22s,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,9)
        self.sz3s.Add(self.sz17s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cCCC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.bm18c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.st20c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.bm19c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz17s.Add(self.st21c,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.bm18cC,0,wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.st5cCCCC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
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
        #[59b]Code VwX...Don't modify[59b]#
        #add your code here

        return #end function

#[win]end your code
