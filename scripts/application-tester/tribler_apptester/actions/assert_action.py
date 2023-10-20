from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.conditional_action import ConditionalAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.screenshot_action import ScreenshotAction


class AssertAction(ActionSequence):

    def __init__(self, test_condition):
        super().__init__()
        self.add_action(ConditionalAction(
            condition=test_condition,
            else_action=ActionSequence(actions=[
                ScreenshotAction(),
                CustomAction(f"raise AssertionError('Assertion fails: %s' % {test_condition!r})")
            ])
        ))
