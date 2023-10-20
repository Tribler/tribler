from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class RemoveRandomDownloadAction(ActionSequence):
    """
    This action will stop a random download.
    """

    def __init__(self):
        super(RemoveRandomDownloadAction, self).__init__()

        self.add_action(PageAction('downloads'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if not window.downloads_page.downloads or len(window.downloads_page.downloads['downloads']) == 0:
    exit_script()
        """))
        self.add_action(ClickAction('window.downloads_list.topLevelItem(randint(0, len(window.downloads_page.download_widgets.keys()) - 1)).progress_slider'))
        self.add_action(WaitAction(1000))
        self.add_action(ClickAction('window.remove_download_button'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if not window.downloads_page.dialog:
    exit_script()
        """))
        self.add_action(ClickAction('window.downloads_page.dialog.buttons[1]'))
        self.add_action(WaitAction(1000))

    def required_imports(self):
        return ["from random import randint"]
