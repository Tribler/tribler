import os
import shutil

from twisted.internet.defer import succeed

from Tribler.community.allchannel2.community import AllChannel2Community
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
import Tribler.Test as super_module
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.util import twisted_wrapper


class FakeDownloadConfig(object):

    def __init__(self, download_dir):
        self.download_dir = download_dir

    def get_dest_dir(self):
        return self.download_dir


class FakeDownload(object):

    def __init__(self, download_dir):
        self.deferred_finished = succeed(self)
        self.dlconfig = FakeDownloadConfig(download_dir)


class FakeSession(object):

    def __init__(self, download_dir):
        self.magnet_links = {}
        self.download_dir = download_dir

    def start_download_from_uri(self, magnetlink, _):
        self.magnet_links[magnetlink] = ''
        return succeed(FakeDownload(self.download_dir))


class TestAllChannel2(TestBase):

    def setUp(self):
        super(TestAllChannel2, self).setUp()

        mocked_community = AllChannel2Community
        key = ECCrypto().generate_key(u"very-low")
        mocked_community.master_peer = Peer(key)
        self.initialize(mocked_community, 2)

        data_dir = os.path.abspath(os.path.join(os.path.dirname(super_module.__file__), 'data', 'channels'))
        for node in self.nodes:
            node.overlay.working_directory = data_dir

    def tearDown(self):
        super(TestAllChannel2, self).tearDown()

        for node in self.nodes:
            channel_dir = os.path.abspath(os.path.join(node.overlay.working_directory, node.overlay.my_channel_name))
            if os.path.isdir(channel_dir):
                shutil.rmtree(channel_dir)

    def test_write_channel(self):
        """
        Check if we can add a magnet link to our channel and write it to file.
        """
        magnet_link = 'a'*20
        self.nodes[0].overlay.add_magnetlink(magnet_link)
        channel_name = self.nodes[0].overlay.my_channel_name

        self.assertListEqual([channel_name], self.nodes[0].overlay.get_channels())
        self.assertListEqual([magnet_link], self.nodes[0].overlay.get_magnetlinks(channel_name))
        self.assertEqual('\xc9\x18[5\x1c\x99=\xe9\x17\xd7|\x0ee\xf6E=ia\xb5W',
                         self.nodes[0].overlay.my_channel_info_hash)

    def test_read_channel(self):
        """
        Check if we can read a channel from disk.
        """
        channel_name = "testcase0"
        magnet_link = 'a' * 20
        self.nodes[0].overlay.load_channel(channel_name)

        self.assertListEqual([channel_name], self.nodes[0].overlay.get_channels())
        self.assertListEqual([magnet_link], self.nodes[0].overlay.get_magnetlinks(channel_name))

    @twisted_wrapper
    def test_share_channel(self):
        """
        Check if peers start downloading each others channel after introducing.
        """
        magnet_link = 'a' * 20
        for node in self.nodes:
            node.overlay.tribler_session = FakeSession(node.overlay.working_directory)
            node.overlay.add_magnetlink(magnet_link)

        yield self.introduce_nodes()
        yield self.deliver_messages()

        for node in self.nodes:
            self.assertListEqual(['magnet:?xt=urn:btih:\xc9\x18[5\x1c\x99=\xe9\x17\xd7|\x0ee\xf6E=ia\xb5W'],
                                 node.overlay.tribler_session.magnet_links.keys())
