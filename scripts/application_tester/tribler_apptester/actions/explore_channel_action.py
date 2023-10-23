from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction, RandomTableViewClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class ExploreChannelAction(ActionSequence):
    """
    This action will 'explore' a discovered channel.
    """

    def __init__(self):
        super(ExploreChannelAction, self).__init__()

        self.add_action(PageAction('discovered'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if window.discovered_page.content_table.model().rowCount() == 0:
    exit_script()
        """))
        self.add_action(RandomTableViewClickAction('window.discovered_page.content_table'))
        self.add_action(WaitAction(2000))
        self.add_action(ClickAction('window.discovered_page.channel_back_button'))
