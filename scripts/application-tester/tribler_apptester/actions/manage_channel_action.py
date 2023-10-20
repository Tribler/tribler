import random
import string
from binascii import hexlify

from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction, RandomTableViewClickAction
from tribler_apptester.actions.conditional_action import ConditionalAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class ManageChannelAction(ActionSequence):
    """
    This action will manage your channel. It works as follows: first, it opens the page of your channel.
    It checks whether there already is a channel created, and if not, it will create one.
    """

    def __init__(self):
        super(ManageChannelAction, self).__init__()

        self.add_action(PageAction('my_channel'))
        self.add_action(WaitAction(1000))

        # Create a new channel if it is not there yet
        add_new_channel_click = ClickAction("window.personal_channel_page.new_channel_button")
        self.add_action(ConditionalAction("window.personal_channel_page.content_table.model().rowCount() == 0",
                                          add_new_channel_click))
        self.add_action(WaitAction(1000))

        # Go to a random channel
        self.add_action(RandomTableViewClickAction('window.personal_channel_page.content_table'))
        self.add_action(WaitAction(2000))

        # Add content
        self.add_action(CustomAction("window.personal_channel_page.on_add_torrent_from_url()"))
        self.add_action(WaitAction(1000))

        random_infohash = hexlify(random.getrandbits(20*8).to_bytes(20, byteorder='big')).decode()
        random_name = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20))

        magnet_link = "magnet:?xt=urn:btih:%s&dn=%s&tr=udp://tracker.openbittorrent.com:80" % (random_infohash, random_name)
        self.add_action(CustomAction("window.personal_channel_page.dialog.dialog_widget.dialog_input.setText('%s')" % magnet_link))
        self.add_action(WaitAction(500))
        self.add_action(ClickAction("window.personal_channel_page.dialog.buttons[1]"))
        self.add_action(WaitAction(1000))
        self.add_action(ClickAction("window.personal_channel_page.channel_back_button"))
