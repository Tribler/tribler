from tribler_apptester.action import Action


class ConditionalAction(Action):
    """
    This action is only executed when a specified condition evaluates to true.
    """

    def __init__(self, condition, if_action=None, else_action=None):
        self.condition = condition
        self.if_action = if_action
        self.else_action = else_action

    @staticmethod
    def indent(code):
        return '\n'.join("    " + line for line in code.split("\n"))

    def get_required_imports(self):
        result = set(self.required_imports())
        if self.if_action:
            result.update(self.if_action.get_required_imports())
        if self.else_action:
            result.update(self.else_action.get_required_imports())
        return sorted(result)

    def action_code(self):
        code = "if " + self.condition + ":\n"
        code += self.indent(self.if_action.action_code() if self.if_action else "pass")
        if self.else_action:
            code += "\nelse:\n" + self.indent(self.else_action.action_code())
        return code
