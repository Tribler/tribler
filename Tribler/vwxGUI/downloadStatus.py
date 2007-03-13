# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class statusDownloads(wx.Panel):
    def __init__(self,parent,id = -1, pos = wx.Point(0,0), size = wx.Size(300,300), style = wx.TAB_TRAVERSAL, name = "panel"):
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
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/triblerpanel_topright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/statusdownloads_bottom.png",wx.BITMAP_TYPE_PNG)
        self.pn9cImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.pn11cImg0=self.fileImgBuf[2];
        self.pn12cImg0=self.fileImgBuf[3];
        self.Show(True)
        self.pn9c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.pn9c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9c_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(220,21))
        self.pn10c.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st42c = wx.StaticText(self.pn10c,-1,"",wx.Point(0,4),wx.Size(107,17),wx.ST_NO_AUTORESIZE)
        self.st42c.SetLabel("Downloading (4)")
        self.st42c.SetForegroundColour(wx.Colour(255,255,255))
        self.st42c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn11c = wx.Panel(self,-1,wx.Point(290,0),wx.Size(10,21))
        self.pn11c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11c_VwXEvOnEraseBackground)
        self.pn12c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(298,55))
        self.pn12c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn12c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn12c_VwXEvOnEraseBackground)
        self.st45c = wx.StaticText(self.pn12c,-1,"",wx.Point(8,0),wx.Size(217,265),wx.ST_NO_AUTORESIZE)
        self.st45c.SetLabel("Dit was het nieuws\r\nNos 8 uur Journaal -24 jan. 2007\r\n")
        self.st45c.SetForegroundColour(wx.Colour(0,0,0))
        self.st45c.SetBackgroundColour(wx.Colour(255,255,255))
        self.st46c = wx.StaticText(self.pn12c,-1,"",wx.Point(308,0),wx.Size(42,269),wx.ST_NO_AUTORESIZE)
        self.st46c.SetLabel("70%\r\n33%")
        self.st46c.SetBackgroundColour(wx.Colour(255,255,255))
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz8s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz43s = wx.BoxSizer(wx.VERTICAL)
        self.sz44s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz8s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn12c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn9c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.SetItemMinSize(self.pn10c,20,10)
        self.sz8s.Add(self.pn11c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz43s.Add(self.st42c,1,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.sz44s.Add(self.st45c,0,wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,8)
        self.sz44s.Add(self.st46c,0,wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,8)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn10c.SetSizer(self.sz43s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
        self.pn12c.SetSizer(self.sz44s);self.pn12c.SetAutoLayout(1);self.pn12c.Layout();
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
    def VwXpn9c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn9c,self.pn9cImg0,0)
        self.pn9c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10c,self.pn10cImg0,2)
        self.pn10c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn11c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn11c,self.pn11cImg0,0)
        self.pn11c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn12c_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn12c,self.pn12cImg0,0)
        self.pn12c_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def pn12c_VwXEvOnEraseBackground(self,event): #init function
        #[ 56]Code event VwX...Don't modify[ 56]#
        #add your code here
        event.Skip()

        return #end function


    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[4db]Code event VwX...Don't modify[4db]#
        #add your code here
        event.Skip()

        return #end function

    def pn11c_VwXEvOnEraseBackground(self,event): #init function
        #[4dd]Code event VwX...Don't modify[4dd]#
        #add your code here
        event.Skip()

        return #end function

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[4dc]Code event VwX...Don't modify[4dc]#
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
        #[4da]Code VwX...Don't modify[4da]#
        #add your code here

        return #end function

#[win]end your code
