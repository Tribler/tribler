# written by Niels Zeilemaker
# see LICENSE.txt for license information

import unittest
import binascii
import os
from threading import Event
from traceback import print_exc


# Import WX after selecting the version
from Tribler.Test.test_as_server import TestGuiAsServer, TESTS_DATA_DIR, wx

from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.CreateTorrentDialog import CreateTorrentDialog
from Tribler.Main.Dialogs.SaveAs import SaveAs
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Main.vwxGUI.list_item import ChannelListItem
from Tribler.Main.vwxGUI.settingsDialog import SettingsDialog


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
            try:
                dialog.saveAll(FakeEvent(saved_event))
            except:
                print_exc()
            dialog.EndModal(wx.ID_CANCEL)

            self.assert_(saved_event.is_set(), 'did not save dialog')
            self.callLater(1, self.quit)

        def do_settings():
            self.callLater(5, do_assert)
            self.frame.top_bg.OnSettings(None)

        self.startTest(do_settings, min_callback_delay=2)

    def test_remove_dialog(self):
        infohash = binascii.unhexlify('66ED7F30E3B30FA647ABAA19A36E7503AA071535')

        def do_assert():
            dialog = wx.FindWindowByName('RemoveTorrent')
            self.assert_(isinstance(dialog, RemoveTorrent), 'could not find RemoveTorrent')

            self.screenshot('Screenshot of RemoveTorrent', window=dialog)
            self.callLater(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.callLater(2, self.quit)

        def item_shown_in_list():
            self.callLater(1, do_assert)
            self.frame.librarylist.Select(infohash)
            self.frame.top_bg.OnDelete()

        def download_object_ready():
            self.CallConditional(10, lambda: infohash in self.frame.librarylist.list.items, item_shown_in_list,
                                 'no download in librarylist')

        def do_downloadfromfile():
            self.guiUtility.showLibrary()
            self.frame.startDownload(os.path.join(TESTS_DATA_DIR, "Pioneer.One.S01E06.720p.x264-VODO.torrent"),
                                     self.getDestDir())

            self.CallConditional(30, lambda: self.session.get_download(infohash), download_object_ready)

        self.startTest(do_downloadfromfile)

    def test_save_dialog(self):
        def do_assert(add_dialog):
            dialog = wx.FindWindowByName('SaveAsDialog')
            self.assert_(isinstance(dialog, SaveAs), 'could not find SaveAs')

            self.screenshot('Screenshot of SaveAs', window=dialog)
            self.callLater(1, lambda: dialog and dialog.EndModal(wx.ID_CANCEL))
            self.callLater(2, lambda: add_dialog and add_dialog.EndModal(wx.ID_CANCEL))
            self.callLater(3, self.quit)

        def do_save_dialog():
            dialog = wx.FindWindowByName('AddTorrentDialog')
            self.assert_(isinstance(dialog, AddTorrent), 'could not find AddTorrent')

            self.callLater(1, lambda: do_assert(dialog))
            dialog.magnet.SetValue(r'http://torrent.fedoraproject.org/torrents/Fedora-20-i386-DVD.torrent')
            dialog.OnAdd(None)

        def do_add_dialog():
            self.guiUtility.utility.write_config('showsaveas', 1)

            self.callLater(1, do_save_dialog)
            self.frame.top_bg.OnAdd(None)

        self.startTest(do_add_dialog)

    def test_feedbackdialog(self):
        def do_assert():
            dialog = wx.FindWindowByName('FeedbackWindow')
            self.assert_(isinstance(dialog, wx.Dialog), 'could not find FeedbackWindow')

            self.screenshot('Screenshot of FeedbackWindow', window=dialog)
            self.callLater(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.callLater(2, self.quit)

        def do_error():
            self.callLater(1, do_assert)
            try:
                raise RuntimeError("Unit-testing")

            except Exception, e:
                self.guiUtility.utility.app.onError(e)

        self.startTest(do_error, min_callback_delay=10)

    def test_add_save_create_dialog(self):
        def do_assert_create(add_dialog):
            dialog = wx.FindWindowByName('CreateTorrentDialog')
            self.assert_(isinstance(dialog, CreateTorrentDialog), 'could not find CreateTorrent')

            self.screenshot('Screenshot of CreateTorrent', window=dialog)
            self.callLater(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.callLater(2, lambda: add_dialog.EndModal(wx.ID_CANCEL))
            self.callLater(3, self.quit)

        def do_assert_add():
            self.callLater(1, lambda: do_assert_create(dialog))

            dialog = wx.FindWindowByName('AddTorrentDialog')
            self.assert_(isinstance(dialog, AddTorrent), 'could not find AddTorrent')

            self.screenshot('Screenshot of AddTorrent', window=dialog)
            dialog.OnCreate(None)

        def do_add_dialog():
            self.callLater(1, do_assert_add)

            managefiles = self.managechannel.fileslist
            managefiles.OnAdd(None)

        def do_create():
            self.managechannel = self.frame.managechannel

            self.managechannel.name.SetValue('UNITTEST')
            self.managechannel.description.SetValue('Channel created for UNITTESTING purposes')

            self.managechannel.Save()

            self.CallConditional(60, lambda: self.frame.managechannel.channel, do_add_dialog,
                                 'Channel instance did not arrive at managechannel')

        def disable_dispersy():
            from Tribler.dispersy.endpoint import NullEndpoint

            dispersy = self.session.get_dispersy_instance()
            dispersy._endpoint = NullEndpoint()
            dispersy._endpoint.open(dispersy)

            self.guiUtility.ShowPage('mychannel')
            self.callLater(1, do_create)

        self.startTest(disable_dispersy)

    def test_confirmationdialog(self):
        def do_assert():
            dialog = wx.FindWindowByName('MFdialog')
            self.assert_(isinstance(dialog, ConfirmationDialog), 'could not find ConfirmationDialog')

            self.screenshot('Screenshot of ConfirmationDialog', window=dialog)
            self.callLater(1, lambda: dialog.EndModal(wx.ID_CANCEL))
            self.callLater(2, self.quit)

        def do_mark(item):
            self.assert_(isinstance(item, ChannelListItem), 'do_mark called without a ChannelListItem')

            self.callLater(10, do_assert)
            self.guiUtility.MarkAsFavorite(None, item.original_data)

        def do_favorite():
            self.assert_(self.frame.searchlist.GetNrChannels() > 0, 'no channels')

            items = self.frame.searchlist.GetItems()
            for _, item in items.iteritems():
                if isinstance(item, ChannelListItem):
                    do_mark(item)
                    break
            else:
                self.assert_(False, 'could not find ChannelListItem')

        def do_search():
            items = self.frame.channellist.GetItems()
            if items:
                do_mark(items.itervalues().next())
            else:
                self.guiUtility.dosearch(u'mp3')
                self.callLater(10, do_favorite)

        def wait_for_channel():
            def has_connections_or_channel():
                if self.frame.SRstatusbar.GetChannelConnections() > 10:
                    return True
                if self.frame.channellist.GetItems():
                    return True

                self.frame.channellist.GetManager().refresh()
                return False

            self.CallConditional(300, has_connections_or_channel, do_search,
                                 'did not connect to more than 10 peers within 300s')

        self.startTest(wait_for_channel)

    def test_debugframe(self):
        def do_screenshot(dialog):
            self.screenshot('Screenshot of DispersyDebugFrame', window=dialog)

            self.callLater(1, dialog.Destroy)
            self.callLater(2, self.quit)

        def do_screenshot_tab():
            dialog = wx.FindWindowByName('DispersyDebugFrame')
            self.assert_(isinstance(dialog, wx.Frame), 'could not find DispersyDebugFrame')

            self.screenshot('Screenshot of DispersyDebugFrame', window=dialog)

            dialog.SwitchTab(1)
            self.callLater(1, lambda: do_screenshot(dialog))

        def do_error():
            self.frame.OnOpenDebugFrame()
            self.callLater(20, do_screenshot_tab)

        self.startTest(do_error, min_callback_delay=5)

if __name__ == "__main__":
    unittest.main()
