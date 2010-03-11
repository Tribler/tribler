import wx
import os, sys

DEBUG = False

class CustomStaticText(wx.StaticText):
#    LINE_HEIGHT = wx.StaticText(None, -1, "foo").GetFont().GetPixelSize().GetHeight()

    def __init__(self, parent, id, label, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0, name="staticText"):
        if DEBUG:
            print >> sys.stderr, size, "->", wx.Size(size.GetWidth(), size.GetHeight())
        size = wx.Size(size.GetWidth(), size.GetHeight())
        style |= wx.ST_NO_AUTORESIZE
        wx.StaticText.__init__(self, parent, id, label, pos, size, style, name)

    def SetFontWeight(self, weight):
        assert weight in (wx.BOLD, wx.NORMAL, wx.LIGHT)
        font = self.GetFont()
        font.SetWeight(weight)
        self.SetFont(font)

    def SetFont(self, font):
        newFont = self.GetFont()
        newFont.SetWeight(font.GetWeight())
        newFont.SetFamily(font.GetFamily())
        newFont.SetPointSize(font.GetPointSize())
        newFont.SetFaceName(font.GetFaceName())
        newFont.SetStyle(font.GetStyle())
        LINE_HEIGHT = newFont.GetPixelSize().GetHeight()
        newFont.SetPixelSize((font.GetPixelSize()[0],LINE_HEIGHT))
        wx.StaticText.SetFont(self, newFont)
