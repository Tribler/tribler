# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
from triblerList import *
from tribler_topButton import *
#[inc]add your include files here

#[inc]end your include

class filesTab_files(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,348),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.st209cCC = wx.StaticText(self,-1,"",wx.Point(8,8),wx.Size(129,18),wx.ST_NO_AUTORESIZE)
        self.st209cCC.SetLabel("number of included files:")
        self.filesField = wx.StaticText(self,-1,"",wx.Point(137,8),wx.Size(86,18),wx.ST_NO_AUTORESIZE)
        self.filesField.SetLabel("unknown")
        self.st209cCCC = wx.StaticText(self,-1,"",wx.Point(8,31),wx.Size(44,18),wx.ST_NO_AUTORESIZE)
        self.st209cCCC.SetLabel("tracker:")
        self.trackerField = wx.StaticText(self,-1,"",wx.Point(52,31),wx.Size(181,18),wx.ST_NO_AUTORESIZE)
        self.trackerField.SetLabel("unknown")
        self.includedFiles = FilesList(self,-1,wxDefaultPosition,wxDefaultSize)
        self.includedFiles.SetDimensions(3,64,292,155)
        self.download = tribler_topButton(self, -1, wx.Point(240,3), wx.Size(55,55))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz237s = wx.BoxSizer(wx.HORIZONTAL)
        self.downloadSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vert = wx.BoxSizer(wx.VERTICAL)
        self.hor_tracker = wx.BoxSizer(wx.HORIZONTAL)
        self.hor_numfiles = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz237s,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.includedFiles,1,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz237s.Add(self.downloadSizer,1,wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.downloadSizer.Add(self.vert,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add([7,55],1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.downloadSizer.Add(self.download,0,wx.FIXED_MINSIZE,3)
        self.vert.Add(self.hor_numfiles,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.vert.Add(self.hor_tracker,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.hor_tracker.Add(self.st209cCCC,0,wx.LEFT|wx.FIXED_MINSIZE,5)
        self.hor_tracker.Add(self.trackerField,0,wx.FIXED_MINSIZE,5)
        self.hor_numfiles.Add(self.st209cCC,0,wx.TOP|wx.LEFT|wx.FIXED_MINSIZE,5)
        self.hor_numfiles.Add(self.filesField,0,wx.TOP|wx.FIXED_MINSIZE,5)
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
        #[2a8]Code VwX...Don't modify[2a8]#
        #add your code here

        return #end function

#[win]end your code
