import random
from pathlib import Path
from typing import Optional

from tribler_apptester.action import Action
from tribler_apptester.actions.change_anonymity_action import ChangeAnonymityAction
from tribler_apptester.actions.change_download_files_action import ChangeDownloadFilesAction
from tribler_apptester.actions.explore_download_action import ExploreDownloadAction
from tribler_apptester.actions.page_action import RandomPageAction
from tribler_apptester.actions.remove_download_action import RemoveRandomDownloadAction
from tribler_apptester.actions.screenshot_action import ScreenshotAction
from tribler_apptester.actions.search_action import RandomSearchAction
from tribler_apptester.actions.start_download_action import StartRandomDownloadAction
from tribler_apptester.actions.start_vod_action import StartVODAction
from tribler_apptester.actions.test_exception import TestExceptionAction


class ActionSelector:
    """ This class is responsible for selecting a random action based on the probabilities given to each action."""

    def __init__(self):
        self.actions_with_probabilities = {
            'test_exception': (lambda: TestExceptionAction(), 0),
            'random_page': (lambda: RandomPageAction(), 20),
            'search': (lambda: RandomSearchAction(), 15),
            'start_download': (lambda: StartRandomDownloadAction(Path(__file__).parent / "data/torrent_links.txt"), 15),
            'remove_download': (lambda: RemoveRandomDownloadAction(), 5),
            'explore_download': (lambda: ExploreDownloadAction(), 10),
            'screenshot': (lambda: ScreenshotAction(), 5),
            'start_vod': (lambda: StartVODAction(), 5),
            'change_anonymity': (lambda: ChangeAnonymityAction(allow_plain=True), 5),
            'change_download_files': (lambda: ChangeDownloadFilesAction(), 10)
        }

    def get_random_action_with_probability(self) -> Optional[Action]:
        """ Returns a random action based on the probabilities given to each action."""
        actions, probabilities = zip(*self.actions_with_probabilities.values())
        choices = random.choices(actions, weights=probabilities, k=1)
        return choices[0]() if choices else None
