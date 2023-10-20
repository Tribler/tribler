from random import choice

from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.assert_action import AssertAction
from tribler_apptester.actions.click_action import ClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.wait_action import WaitAction


class StartDownloadAction(ActionSequence):
    """
    This action will start a download from a given URI.
    """

    def __init__(self, download_uri):
        super(StartDownloadAction, self).__init__()

        self.add_action(CustomAction("window.on_add_torrent_from_url()"))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("window.dialog.dialog_widget.dialog_input.setText('%s')" % download_uri))
        self.add_action(WaitAction(1000))
        self.add_action(ClickAction("window.dialog.buttons[0]"))
        self.add_action(WaitAction(7000))
        self.add_action(AssertAction("hasattr(window.dialog.dialog_widget, 'download_button')"))
        self.add_action(ClickAction("window.dialog.dialog_widget.download_button"))
        self.add_action(WaitAction(2000))


class StartRandomDownloadAction(StartDownloadAction):
    """
    Start a random download from a pre-defined list.
    """

    def __init__(self, magnets_file_path):
        with open(magnets_file_path) as torrent_links_file:
            content = torrent_links_file.read()
            links = content.split('\n')[:-1]  # Remove the newline

        rand_link = choice(links)

        super(StartRandomDownloadAction, self).__init__(rand_link)
