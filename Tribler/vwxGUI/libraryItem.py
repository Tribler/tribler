# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from tribler_topButton import *
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
        self.Show(True)
        self.SetBackgroundColour(wx.Colour(255,255,255))
        self.st5c = wx.StaticText(self,-1,"",wx.Point(58,3),wx.Size(162,14),wx.ST_NO_AUTORESIZE)
        self.st5c.SetLabel("NOS 8 Uur Journaal van...")
        self.st5c.SetFont(wx.Font(8,74,90,90,0,"Verdana"))
        self.st13c = wx.StaticText(self,-1,"",wx.Point(61,20),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st13c.SetLabel("video (avi) 01m32")
        self.st13c.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCC = wx.StaticText(self,-1,"",wx.Point(171,10),wx.Size(87,15),wx.ST_NO_AUTORESIZE)
        self.st5cCC.SetLabel("progress pic")
        self.st5cCC.SetForegroundColour(wx.Colour(255,85,0))
        self.ck17c = wx.CheckBox(self,-1,"",wx.Point(258,3),wx.Size(13,13))
        self.st5cC = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(77,15),wx.ST_NO_AUTORESIZE)
        self.st5cC.SetLabel("archive")
        self.st5cC.SetForegroundColour(wx.Colour(128,128,128))
        self.ck17cC = wx.CheckBox(self,-1,"",wx.Point(258,18),wx.Size(13,13))
        self.st5cCCCCC = wx.StaticText(self,-1,"",wx.Point(412,18),wx.Size(82,18),wx.ST_NO_AUTORESIZE)
        self.st5cCCCCC.SetLabel("private")
        self.st5cCCCCC.SetForegroundColour(wx.Colour(128,128,128))
        self.st5cCCC = wx.StaticText(self,-1,"",wx.Point(468,10),wx.Size(72,13),wx.ST_NO_AUTORESIZE)
        self.st5cCCC.SetLabel("> play")
        self.st5cCCC.SetForegroundColour(wx.Colour(255,85,0))
        self.pb = wx.Gauge(self,-1,100,wx.Point(362,6),wx.Size(99,12),wx.GA_HORIZONTAL)
        self.pbText = wx.StaticText(self,-1,"",wx.Point(362,18),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.pbText.SetLabel("text")
        self.pause = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(15,15))
        self.sz3s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz12s = wx.BoxSizer(wx.VERTICAL)
        self.sz14s = wx.BoxSizer(wx.VERTICAL)
        self.sz22s = wx.BoxSizer(wx.VERTICAL)
        self.sz16s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz16sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz12s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cCC,0,wx.TOP|wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz14s,0,wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz22s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.st5cCCC,0,wx.ALIGN_CENTER_VERTICAL|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pause,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.FIXED_MINSIZE,3)
        self.sz12s.Add(self.st5c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz12s.Add(self.st13c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz14s.Add(self.sz16s,0,wx.FIXED_MINSIZE,3)
        self.sz14s.Add(self.sz16sC,0,wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.pb,0,wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz22s.Add(self.pbText,0,wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
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
