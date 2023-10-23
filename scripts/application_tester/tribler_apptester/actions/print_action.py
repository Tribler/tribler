from tribler_apptester.action import Action


class PrintAction(Action):
    """
    This action prints a specific object.
    """

    def __init__(self, print_str, *args):
        super(PrintAction, self).__init__()
        self.print_str = print_str
        self.print_args = args

    def action_code(self):
        args_str = "(%s)" % ", ".join(self.print_args)
        return "print('%s' %% %s)" % (self.print_str, args_str)
