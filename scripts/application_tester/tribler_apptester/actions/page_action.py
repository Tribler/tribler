from random import choice

from tribler_apptester.actions.click_action import ClickSequenceAction


class PageAction(ClickSequenceAction):
    """
    This action goes to a specific page in Tribler.
    """
    BUTTONS_TO_PAGES = {
        'downloads': ['window.left_menu_button_downloads'],
        'search': [],
        'settings': ['window.settings_button'],
    }

    def __init__(self, page_name):
        super(PageAction, self).__init__(self.BUTTONS_TO_PAGES[page_name])


class RandomPageAction(PageAction):
    """
    This action goes to a random page in Tribler.
    """

    def __init__(self):
        rand_page = choice(list(self.BUTTONS_TO_PAGES.keys()))
        super(RandomPageAction, self).__init__(rand_page)
