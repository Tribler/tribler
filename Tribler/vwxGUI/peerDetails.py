# -*- coding: iso-8859-1 -*- 
# Don't modify comment 

import wx
#[inc]add your include files here

#[inc]end your include

class peerDetails(wx.Panel):
    def __init__(self,parent,id = -1,pos = wx.Point(0,0),size = wx.Size(300,462),style = wx.TAB_TRAVERSAL,name = 'panel'):
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
        self.fileImgBuf=[None] * 7
        self.fileImgBuf[0] = wx.Bitmap("images/triblerpanel_topleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[1] = wx.Bitmap("images/triblerpanel_topcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[2] = wx.Bitmap("images/triblerpanel_topright.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[3] = wx.Bitmap("images/2p_90x90.jpg",wx.BITMAP_TYPE_JPEG)
        self.fileImgBuf[4] = wx.Bitmap("images/triblerpanel_bottomleft.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[5] = wx.Bitmap("images/triblerpanel_bottomcenter.png",wx.BITMAP_TYPE_PNG)
        self.fileImgBuf[6] = wx.Bitmap("images/triblerpanel_bottomright.png",wx.BITMAP_TYPE_PNG)
        self.pn9cImg0=self.fileImgBuf[0];
        self.pn10cImg0=self.fileImgBuf[1];
        self.pn11cImg0=self.fileImgBuf[2];
        self.pn15cCImg0=self.fileImgBuf[3];
        self.pn9cCImg0=self.fileImgBuf[4];
        self.pn10cCImg0=self.fileImgBuf[5];
        self.pn11cCImg0=self.fileImgBuf[6];
        self.Show(True)
        self.pn9c = wx.Panel(self,-1,wx.Point(0,0),wx.Size(10,21))
        self.pn9c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9c_VwXEvOnEraseBackground)
        self.pn10c = wx.Panel(self,-1,wx.Point(10,0),wx.Size(0,21))
        self.pn10c.SetForegroundColour(wx.Colour(255,255,255))
        self.pn10c.SetBackgroundColour(wx.Colour(255,51,0))
        self.pn10c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10c_VwXEvOnEraseBackground)
        self.st64c = wx.StaticText(self.pn10c,-1,"",wx.Point(3,3),wx.Size(234,17),wx.ST_NO_AUTORESIZE)
        self.st64c.SetLabel("Jan de Vries")
        self.pn11c = wx.Panel(self,-1,wx.Point(288,0),wx.Size(10,21))
        self.pn11c.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11c.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11c_VwXEvOnEraseBackground)
        self.pn12c = wx.Panel(self,-1,wx.Point(0,21),wx.Size(298,430))
        self.pn12c.SetBackgroundColour(wx.Colour(255,255,255))
        self.pn48c = wx.Panel(self.pn12c,-1,wx.Point(0,0),wx.Size(290,100))
        self.pn48c.SetBackgroundColour(wx.Colour(219,219,219))
        self.pn15cC = wx.Panel(self.pn48c,-1,wx.Point(6,6),wx.Size(90,90),wx.SIMPLE_BORDER)
        self.pn15cC.SetBackgroundColour(wx.Colour(219,219,219))
        self.pn15cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn15cC_VwXEvOnEraseBackground)
        self.st5cCCCCCC = wx.StaticText(self.pn48c,-1,"",wx.Point(105,3),wx.Size(82,45))
        self.st5cCCCCCC.SetLabel("15 downloads")
        self.st5cCCCCCC.SetFont(wx.Font(8,74,90,90,0,"Tahoma"))
        self.st5cCCCCCC.SetForegroundColour(wx.Colour(0,0,0))
        self.pn44c = wx.Panel(self.pn12c,-1,wx.Point(0,100),wx.Size(20,20))
        self.pn44c.SetBackgroundColour(wx.Colour(110,110,110))
        self.pn9cC = wx.Panel(self,-1,wx.Point(3,275),wx.Size(10,28))
        self.pn9cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn9cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn9cC_VwXEvOnEraseBackground)
        self.pn10cC = wx.Panel(self,-1,wx.Point(13,273),wx.Size(155,28))
        self.pn10cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn10cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn10cC_VwXEvOnEraseBackground)
        self.pn11cC = wx.Panel(self,-1,wx.Point(108,432),wx.Size(190,28))
        self.pn11cC.SetBackgroundColour(wx.Colour(0,0,0))
        self.pn11cC.Bind(wx.EVT_ERASE_BACKGROUND,self.VwXpn11cC_VwXEvOnEraseBackground)
        self.sz3s = wx.BoxSizer(wx.VERTICAL)
        self.sz8s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz8sC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz13s = wx.BoxSizer(wx.VERTICAL)
        self.sz14sCC = wx.BoxSizer(wx.HORIZONTAL)
        self.sz65s = wx.BoxSizer(wx.HORIZONTAL)
        self.sz3s.Add(self.sz8s,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.pn12c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz3s.Add(self.sz8sC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn9c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.Add(self.pn10c,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8s.SetItemMinSize(self.pn10c,20,10)
        self.sz8s.Add(self.pn11c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn9cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.Add(self.pn10cC,1,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz8sC.SetItemMinSize(self.pn10cC,20,10)
        self.sz8sC.Add(self.pn11cC,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz13s.Add(self.pn48c,0,wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.sz13s.Add(self.pn44c,0,wx.BOTTOM|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz14sCC.Add(self.pn15cC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND|wx.FIXED_MINSIZE,6)
        self.sz14sCC.Add(self.st5cCCCCCC,0,wx.TOP|wx.LEFT|wx.BOTTOM|wx.EXPAND|wx.ALIGN_BOTTOM|wx.FIXED_MINSIZE,8)
        self.sz65s.Add(self.st64c,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,4)
        self.SetSizer(self.sz3s);self.SetAutoLayout(1);self.Layout();
        self.pn12c.SetSizer(self.sz13s);self.pn12c.SetAutoLayout(1);self.pn12c.Layout();
        self.pn48c.SetSizer(self.sz14sCC);self.pn48c.SetAutoLayout(1);self.pn48c.Layout();
        self.pn10c.SetSizer(self.sz65s);self.pn10c.SetAutoLayout(1);self.pn10c.Layout();
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
    def VwXpn15cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn15cC,self.pn15cCImg0,0)
        self.pn15cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn9cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn9cC,self.pn9cCImg0,0)
        self.pn9cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn10cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn10cC,self.pn10cCImg0,2)
        self.pn10cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return
    def VwXpn11cC_VwXEvOnEraseBackground(self,event):
        self.VwXDrawBackImg(event,self.pn11cC,self.pn11cCImg0,0)
        self.pn11cC_VwXEvOnEraseBackground(event)
        event.Skip(False)

        return

#[win]add your code here

    def pn9cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 40]Code event VwX...Don't modify[ 40]#
        #add your code here
        event.Skip()

        return #end function

    def pn9c_VwXEvOnEraseBackground(self,event): #init function
        #[ 3c]Code event VwX...Don't modify[ 3c]#
        #add your code here
        event.Skip()

        return #end function

    def pn15cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 3f]Code event VwX...Don't modify[ 3f]#
        #add your code here
        event.Skip()

        return #end function

    def pn11cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 42]Code event VwX...Don't modify[ 42]#
        #add your code here
        event.Skip()

        return #end function

    def pn11c_VwXEvOnEraseBackground(self,event): #init function
        #[ 3e]Code event VwX...Don't modify[ 3e]#
        #add your code here
        event.Skip()

        return #end function

    def pn10cC_VwXEvOnEraseBackground(self,event): #init function
        #[ 41]Code event VwX...Don't modify[ 41]#
        #add your code here
        event.Skip()

        return #end function

    def pn10c_VwXEvOnEraseBackground(self,event): #init function
        #[ 3d]Code event VwX...Don't modify[ 3d]#
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
        #[ 3b]Code VwX...Don't modify[ 3b]#
        #add your code here

        return #end function

#[win]end your code
