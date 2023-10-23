from tribler_apptester.action import Action


class ActionSequence(Action):
    """
    An action sequence is a list of actions. This allows programmers to define their own complicated sequence.
    """

    def __init__(self, actions=None):
        super().__init__()
        self.actions = actions or []

    def add_action(self, action):
        self.actions.append(action)

    def get_required_imports(self):
        result = set(self.required_imports())
        for action in self.actions:
            result.update(action.get_required_imports())
        return sorted(result)

    def action_code(self):
        return "\n".join(action.action_code() for action in self.actions)
