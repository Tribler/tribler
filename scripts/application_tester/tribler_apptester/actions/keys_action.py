from tribler_apptester.action import Action


class KeysAction(Action):
    """
    This action presses a sequence of keyboard keys.
    """

    def __init__(self, obj_name, key_input, delay):
        super(KeysAction, self).__init__()
        self.obj_name = obj_name
        self.key_input = key_input
        self.delay = delay

    def action_code(self):
        return "QTest.keyClicks(%s, '%s', delay=%d)" % (self.obj_name, self.key_input, self.delay)

    def required_imports(self):
        return ["from PyQt5.QtTest import QTest"]
