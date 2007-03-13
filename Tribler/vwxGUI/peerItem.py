# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class peerItem(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(82,155),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf[0] = wx.Bitmap("images/1p_82x82.gif",wx.BITMAP_TYPE_GIF)
        self.bm4cImg0=self.fileImgBuf[0];
        self.Show(True)
        self.bm4c = wx.StaticBitmap(self,-1,self.bm4cImg0,wx.Point(0,0),wx.Size(82,82),wx.SIMPLE_BORDER)
        self.bm4c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.st5c = wx.StaticText(self,-1,"",wx.Point(0,85),wx.Size(82,28),wx.ST_NO_AUTORESIZE)
        self.st5c.SetLabel("Sanne de Vries")
        self.st5c.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.st5cC = wx.StaticText(self,-1,"",wx.Point(0,116),wx.Size(82,28),wx.ST_NO_AUTORESIZE)
        self.st5cC.SetLabel("15 downloads")
        self.st5cC.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.st5cC.SetForegroundColour(wx.Colour(128,128,128))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz3s.Add(self.bm4c,0,wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cC,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,1)
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
        #[764]Code VwX...Don't modify[764]#
        #add your code here

        return #end function

#[win]end your code
