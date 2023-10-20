from tribler_apptester.action import Action


class WaitAction(Action):
    """
    This action simply waits (non-blocking) for a defined amount of time (in milliseconds).
    """

    def __init__(self, wait_time):
        super(WaitAction, self).__init__()
        self.wait_time = wait_time

    def action_code(self):
        return "QTest.qWait(%d)" % self.wait_time

    def required_imports(self):
        return ["from PyQt5.QtTest import QTest"]
