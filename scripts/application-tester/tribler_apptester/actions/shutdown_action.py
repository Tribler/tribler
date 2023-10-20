from tribler_apptester.action import Action


class ShutdownAction(Action):
    """
    This action shuts down Tribler.
    """
    def action_code(self):
        return "window.close_tribler()"


class HardShutdownAction(Action):
    """
    This action shuts down Tribler in a more forced way.
    """
    def action_code(self):
        return "QApplication.quit()"

    def required_imports(self):
        return ['from PyQt5.QtWidgets import QApplication']
