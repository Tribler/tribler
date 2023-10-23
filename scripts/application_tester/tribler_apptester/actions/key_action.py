from tribler_apptester.action import Action


class KeyAction(Action):
    """
    This action presses a specific keyboard key.
    """

    def __init__(self, obj_name, key_name):
        super(KeyAction, self).__init__()
        self.obj_name = obj_name
        self.key_name = key_name

    def action_code(self):
        return "QTest.keyClick(%s, Qt.%s)" % (self.obj_name, self.key_name)

    def required_imports(self):
        return ["from PyQt5.QtTest import QTest", "from PyQt5.QtCore import Qt"]
