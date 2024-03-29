from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class ChangeAnonymityAction(ActionSequence):
    """
    This action will change the anonymity of a random download.
    """

    def __init__(self, allow_plain=False):
        super(ChangeAnonymityAction, self).__init__()

        self.add_action(PageAction('downloads'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if len(window.downloads_page.download_widgets) == 0:
    exit_script()
        """))
        self.add_action(ClickAction('window.downloads_list.topLevelItem(randint(0, len(window.downloads_page.download_widgets.keys()) - 1)).progress_slider'))
        self.add_action(WaitAction(100))
        min_hops = 0 if allow_plain else 1
        self.add_action(CustomAction("window.downloads_page.change_anonymity(randint(%d, 3))" % min_hops))

    def required_imports(self):
        return ["from random import randint"]
