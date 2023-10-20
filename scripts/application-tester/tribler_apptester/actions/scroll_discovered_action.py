from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.scroll_action import RandomScrollAction
from tribler_apptester.actions.wait_action import WaitAction


class ScrollDiscoveredAction(ActionSequence):
    """
    This action scrolls through the discovered torrents in Tribler.
    """

    def __init__(self):
        super(ScrollDiscoveredAction, self).__init__()

        self.add_action(PageAction('discovered'))
        for _ in range(0, 10):
            self.add_action(RandomScrollAction("window.discovered_page.content_table"))
            self.add_action(WaitAction(300))
