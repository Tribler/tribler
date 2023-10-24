from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction, RandomTableViewClickAction
from tribler_apptester.actions.conditional_action import ConditionalAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.print_action import PrintAction
from tribler_apptester.actions.wait_action import WaitAction


class SubscribeUnsubscribeAction(ActionSequence):
    """
    This action will subscribe/unsubscribe to/from a random channel in the list of discovered channels.
    """

    def __init__(self):
        super(SubscribeUnsubscribeAction, self).__init__()

        self.add_action(PageAction('discovered'))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction("""
model = window.discovered_page.model
if model is None or model.rowCount() == 0:
    exit_script()
    """))
        self.add_action(RandomTableViewClickAction('window.discovered_page.content_table'))
        self.add_action(WaitAction(2000))

        click_action = ClickAction('window.discovered_page.subscribe_button')
        self.add_action(PrintAction("Clicked on channel: %s", "window.discovered_page.model.channel_info"))
        self.add_action(ConditionalAction("window.discovered_page.subscribe_button.isVisible()", click_action))
        self.add_action(WaitAction(2000))
        self.add_action(ClickAction('window.discovered_page.channel_back_button'))
