import logging
import wx
from Tribler.Main.vwxGUI.MainFrame import FileDropTarget


class TriblerApp(wx.App):

    def __init__(self, *args, **kwargs):
        wx.App.__init__(self, *args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._abcapp = None

    def set_abcapp(self, abcapp):
        self._abcapp = abcapp

    def MacOpenFile(self, filename):
        self._logger.info(repr(filename))
        target = FileDropTarget(self._abcapp.frame)
        target.OnDropFiles(None, None, [filename])
