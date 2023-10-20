from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class ExploreDownloadAction(ActionSequence):
    """
    This action will 'explore' an existing download. This means clicking it and clicking on some of the tabs to
    view information about the selected download.
    """

    def __init__(self):
        super(ExploreDownloadAction, self).__init__()

        self.add_action(PageAction('downloads'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if not window.downloads_page.downloads or len(window.downloads_page.downloads['downloads']) == 0:
    exit_script()
        """))
        self.add_action(ClickAction('window.downloads_list.topLevelItem(randint(0, len(window.downloads_page.download_widgets.keys()) - 1)).progress_slider'))
        self.add_action(CustomAction('window.download_details_widget.setCurrentIndex(randint(0, 3))'))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction('window.download_details_widget.setCurrentIndex(randint(0, 3))'))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction('window.download_details_widget.setCurrentIndex(randint(0, 3))'))

    def required_imports(self):
        return ["from random import randint"]
