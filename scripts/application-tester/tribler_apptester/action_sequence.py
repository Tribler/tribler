class ActionSequence(object):
    """
    An action sequence is a list of actions. This allows programmers to define their own complicated sequence.
    """

    def __init__(self):
        self.actions = []

    def add_action(self, action):
        self.actions.append(action)

    def generate_code(self):
        required_imports = set()
        code = ""
        for action in self.actions:
            for required_import in action.required_imports():
                required_imports.add(required_import)
        for required_import in self.required_imports():
            required_imports.add(required_import)

        for required_import in required_imports:
            code += required_import + "\n"

        code += "\n"

        for action in self.actions:
            code += action.action_code() + "\n"

        return code

    def required_imports(self):
        return []
