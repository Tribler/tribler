# Written by Arno Bakker
# see LICENSE.txt for license information

import wx


class BandwidthSelector(wx.Dialog):
    def __init__(self, parent, utility):
        self.parent = parent
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE
        title = self.utility.lang.get('selectbandwidthtitle')
        wx.Dialog.__init__(self,parent,-1,title,style=style,size=(470,180))

        sizer = wx.GridBagSizer(5,20)

        self.bwctrl = BWControl(self)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, label=self.utility.lang.get('ok'), style = wx.BU_EXACTFIT)
        buttonbox.Add(okbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, label=self.utility.lang.get('cancel'), style = wx.BU_EXACTFIT)
        buttonbox.Add(cancelbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)

        explain = wx.StaticText(self, -1, self.utility.lang.get('selectdlulbwexplan'))
        explain.Wrap( 450 )

        prompt = wx.StaticText(self, -1, self.utility.lang.get('selectdlulbwprompt'))
        prompt.Wrap( 450 )

        sizer.Add( explain, (1,1), span=(1,2) )
        sizer.Add( prompt, (2,1) )
        sizer.Add( self.bwctrl, (2,2) )
        sizer.Add( buttonbox, (3,1), span=(2,1) )

        self.SetSizer(sizer)


    def getUploadBandwidth(self):
        return self.bwctrl.getUploadBandwidth()


class BWControl(wx.Panel):

    def __init__(self,parent,*args,**kwargs):

        self.utility = parent.utility

        wx.Panel.__init__(self, parent, -1, *args, **kwargs)

        self.uploadbwvals = [ 128/8, 256/8, 512/8, 1024/8, 2048/8, 0]
        self.bwoptions = ['xxxx/128 kbps', 'xxxx/256 kbps', 'xxxx/512 kbps', 'xxxx/1024 kbps', 'xxxx/2048 kbps', 'more (LAN)']
        self.bwsel = wx.Choice(self,
                                    -1,
                                    #self.utility.lang.get('selectdlulbwprompt'),
                                    wx.DefaultPosition,
                                    wx.DefaultSize,
                                    self.bwoptions,
                                    3)

    def getUploadBandwidth(self):
        """ in Kbyte/s """
        index = self.bwsel.GetSelection()
        return self.uploadbwvals[index]
