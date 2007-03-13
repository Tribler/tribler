# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class wxcus29232f(wx.Panel):
    def __init__(self,parent,id = -1, pos = wx.Point(0,0), size = wx.Size(75,17), style = wx.TAB_TRAVERSAL, name = "panel"):
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
        self.pn3c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(75,20))
        self.st4c = wx.StaticText(self.pn3c,-1,"",wx.Point(0,0),wx.Size(49,13),wx.ST_NO_AUTORESIZE)
        self.st4c.SetLabel("tab")
        self.sz5s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz5s.Add(self.st4c,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.pn3c.SetSizer(self.sz5s);self.pn3c.SetAutoLayout(1);self.pn3c.Layout();
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
        #[6d8]Code VwX...Don't modify[6d8]#
        #add your code here

        return #end function

#[win]end your code
