from tribler_apptester.action import Action


class ConditionalAction(Action):
    """
    This action is only executed when a specified condition evaluates to true.
    """

    def __init__(self, condition, if_action, else_action=None):
        self.condition = condition
        self.if_action = if_action
        self.else_action = else_action

    @staticmethod
    def indent(code):
        lines = code.split("\n")
        for line_ind in range(len(lines)):
            lines[line_ind] = "    " + lines[line_ind]
        return '\n'.join(lines)

    def action_code(self):
        required_imports = set()
        code = ""
        for required_import in self.if_action.required_imports():
            required_imports.add(required_import)
        if self.else_action:
            for required_import in self.else_action.required_imports():
                required_imports.add(required_import)
        for required_import in self.required_imports():
            required_imports.add(required_import)

        for required_import in required_imports:
            code += required_import + "\n"

        code += "\n"

        # Build the if-else clause
        code += "if " + self.condition + ":\n"
        code += ConditionalAction.indent(self.if_action.action_code())
        if self.else_action:
            code += "else:\n"
            code += ConditionalAction.indent(self.else_action.action_code())

        return code
