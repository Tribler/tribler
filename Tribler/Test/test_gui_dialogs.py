# written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import sys
import wx
import binascii
import os

from Tribler.Test.test_as_server import TestGuiAsServer, BASE_DIR
from Tribler.Main.vwxGUI.list_item import ChannelListItem
from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.CreateTorrent import CreateTorrent
from Tribler.Main.Dialogs.SaveAs import SaveAs
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Main.vwxGUI.settingsDialog import SettingsDialog
from threading import Event


class TestGuiDialogs(TestGuiAsServer):

    def test_settings_dialog(self):

        def do_assert():
            dialog = wx.FindWindowByName('settingsDialog')
            self.assert_(isinstance(dialog, SettingsDialog), 'could not find SettingsDialog')

            self.screenshot('Screenshot of SettingsDialog', window=dialog)

            saved_event = Event()
            class FakeEvent():
                def __init__(self, event):
                    self.event = event

                def Skip(self):
                    self.event.set()
            dialog.saveAll(FakeEvent(saved_event))
            dialog.EndModal(wx.ID_CANCEL)
            
            self.assert_(saved_event.is_set(), 'did not save dialog within 10s')
            self.Call(1, self.quit)

        def do_settings():
            self.Call(1, do_assert)
            self.frame.top_bg.OnSettings(None)

        self.startTest(do_settings, min_timeout=10)

    def test_remove_dialog(self):
        infohash = binascii.unhexlify('66ED7F30E3B30FA647ABAA19A36E7503AA071535')

        def do_assert():
            dialog = wx.FindWindowByName('RemoveTorrent')
            self.assert_(isinstance(dialog, RemoveTorrent), 'could not find RemoveTorrent')

            self.screenshot('Screenshot of RemoveTorrent', window=dialog)
            self.Call(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.Call(2, self.quit)

        def item_shown_in_list():
            self.Call(1, do_assert)
            self.frame.librarylist.Select(infohash)
            self.frame.top_bg.OnDelete()

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list, 'no download in librarylist')

        def do_downloadfromfile():
            self.guiUtility.showLibrary()
            self.frame.startDownload(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"), self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_downloadfromfile)

    def test_save_dialog(self):
        def do_assert(add_dialog):
            dialog = wx.FindWindowByName('SaveAsDialog')
            self.assert_(isinstance(dialog, SaveAs), 'could not find SaveAs')

            self.screenshot('Screenshot of SaveAs', window=dialog)
            self.Call(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.Call(2, lambda: add_dialog.EndModal(wx.ID_CANCEL))
            self.Call(3, self.quit)

        def do_save_dialog():
            dialog = wx.FindWindowByName('AddTorrentDialog')
            self.assert_(isinstance(dialog, AddTorrent), 'could not find AddTorrent')

            self.Call(1, lambda: do_assert(dialog))
            dialog.magnet.SetValue(r'http://www.clearbits.net/get/1763-zenith-part-2.torrent')
            dialog.OnAdd(None)

        def do_add_dialog():
            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            defaultDLConfig.set_show_saveas(True)

            self.Call(1, do_save_dialog)
            self.frame.top_bg.OnAdd(None)

        self.startTest(do_add_dialog)

    def test_feedbackdialog(self):
        def do_assert():
            dialog = wx.FindWindowByName('FeedbackWindow')
            self.assert_(isinstance(dialog, wx.Dialog), 'could not find FeedbackWindow')

            self.screenshot('Screenshot of FeedbackWindow', window=dialog)
            self.Call(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.Call(2, self.quit)

        def do_error():
            self.Call(1, do_assert)
            try:
                raise RuntimeError("Unit-testing")

            except Exception, e:
                self.guiUtility.utility.app.onError(e)

        self.startTest(do_error, min_timeout=10)

    def test_add_save_create_dialog(self):
        def do_assert_create(add_dialog):
            dialog = wx.FindWindowByName('CreateTorrentDialog')
            self.assert_(isinstance(dialog, CreateTorrent), 'could not find CreateTorrent')

            self.screenshot('Screenshot of CreateTorrent', window=dialog)
            self.Call(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.Call(2, lambda: add_dialog.EndModal(wx.ID_CANCEL))
            self.Call(3, self.quit)

        def do_assert_add():
            self.Call(1, lambda: do_assert_create(dialog))

            dialog = wx.FindWindowByName('AddTorrentDialog')
            self.assert_(isinstance(dialog, AddTorrent), 'could not find AddTorrent')

            self.screenshot('Screenshot of AddTorrent', window=dialog)
            dialog.OnCreate(None)

        def do_add_dialog():
            self.Call(1, do_assert_add)

            managefiles = self.managechannel.fileslist
            managefiles.OnAdd(None)

        def do_create():
            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()

            self.CallConditional(60, lambda: self.frame.managechannel.channel, do_add_dialog, 'Channel instance did not arrive at managechannel')

        def disable_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)

            self.guiUtility.ShowPage('mychannel')
            self.Call(1, do_create)

        self.startTest(disable_dispersy)

    def test_confirmationdialog(self):
        def do_assert():
            dialog = wx.FindWindowByName('MFdialog')
            self.assert_(isinstance(dialog, ConfirmationDialog), 'could not find ConfirmationDialog')

            self.screenshot('Screenshot of ConfirmationDialog', window=dialog)
            self.Call(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.Call(2, self.quit)

        def do_favorite():
            self.assert_(self.frame.searchlist.GetNrChannels() > 0, 'no channels')

            items = self.frame.searchlist.GetItems()
            for _, item in items.iteritems():
                if isinstance(item, ChannelListItem):
                    self.Call(10, do_assert)
                    self.guiUtility.MarkAsFavorite(None, item.original_data)
                    break
            else:
                self.assert_(False, 'could not find ChannelListItem')


        def do_search():
            self.guiUtility.dosearch(u'mp3')
            self.Call(10, do_favorite)

        def wait_for_search():
            self.CallConditional(300, lambda: self.frame.SRstatusbar.GetChannelConnections() > 5, do_search, 'did not connect to more than 5 peers within 300s')

        self.startTest(wait_for_search)

if __name__ == "__main__":
    unittest.main()
