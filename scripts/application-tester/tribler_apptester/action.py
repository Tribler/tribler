from abc import abstractmethod


class Action(object):
    """
    An action is a small unit that consists of one or more simple steps that can be achieved by running one or more
    lines of code. Examples of actions are clicking a button, waiting for a pre-defined amount of time or going to a
    specific page in a Tribler instance.

    This is an abstract class and each subclass of Action should define the following:
    - an implementation for the generate_code class, which is expected to return a string with code
    - a list of required imports to run the code returned by generate_code
    """

    @abstractmethod
    def action_code(self):
        pass

    def generate_code(self):
        code = ""
        for import_line in self.required_imports():
            code += import_line + "\n"
        code += "\n"
        code += self.action_code()
        return code

    def required_imports(self):
        return []
