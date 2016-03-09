from binascii import hexlify
from Tribler.Test.common import UBUNTU_1504_INFOHASH
from Tribler.Test.test_as_server import TestGuiAsServer
from Tribler.Utilities.Instance2Instance import Instance2InstanceClient


class TestI2IDownload(TestGuiAsServer):

    def test_i2i_running(self):

        def make_screenshot():
            self.screenshot('After starting an I2I magnet download')
            self.quit()

        def item_shown_in_list():
            self.CallConditional(60, lambda: self.frame.librarylist.list.GetItem(UBUNTU_1504_INFOHASH)
                                 .original_data.ds and self.frame.librarylist.list.GetItem(UBUNTU_1504_INFOHASH),
                                 make_screenshot, 'no download progress')

        def download_object_ready():
            self.CallConditional(10, lambda: self.frame.librarylist.list.HasItem(
                UBUNTU_1504_INFOHASH), item_shown_in_list, 'no download in librarylist')

        def do_test_i2i():
            self.guiUtility.utility.write_config('showsaveas', 0)
            i2i_port = self.app._abcapp.utility.read_config('i2ilistenport')
            magnet_link = r'magnet:?xt=urn:btih:%s&dn=ubuntu-14.04.2-desktop-amd64.iso' \
                          % hexlify(UBUNTU_1504_INFOHASH)
            self.assertTrue(Instance2InstanceClient(i2i_port, 'START', magnet_link))

            self.CallConditional(30, lambda: self.session.get_download(UBUNTU_1504_INFOHASH), download_object_ready,
                                 'Adding torrent from I2I failed')

        self.startTest(do_test_i2i, allow_multiple=False)
