from tribler_apptester.action import Action


class RandomScrollAction(Action):
    """
    This action scrolls a specific view (that has a horizontal or vertical scrollbar attached).
    """

    def __init__(self, obj_name):
        super(RandomScrollAction, self).__init__()
        self.obj_name = obj_name

    def action_code(self):
        return "%s.verticalScrollBar().setValue(randint(%s.verticalScrollBar().minimum(), %s.verticalScrollBar().maximum()))" % (self.obj_name, self.obj_name, self.obj_name)

    def required_imports(self):
        return ["from random import randint"]
