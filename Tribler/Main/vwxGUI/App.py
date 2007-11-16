# -*- coding: iso-8859-1 -*-
import wx

provider = wx.SimpleHelpProvider()
wx.HelpProvider_Set(provider)

import MyFrame


class App(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        self.main = MyFrame.MyFrame(None,-1,'')
        self.main.Show()
        self.SetTopWindow(self.main)
        return 1

def main():
    application = App(0)
    application.MainLoop()

if __name__ == '__main__':
    main()
