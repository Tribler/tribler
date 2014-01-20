# Written by Egbert Bouman
# see LICENSE.txt for license information

import ast

from ConfigParser import RawConfigParser

from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException


class CallbackConfigParser(RawConfigParser):

    def __init__(self, *args, **kwargs):
        RawConfigParser.__init__(self, *args, **kwargs)
        self.callback = None

    def set_callback(self, callback):
        self.callback = callback

    def set(self, section, option, new_value):
        if self.callback and self.has_section(section) and self.has_option(section, option):
            old_value = self.get(section, option)
            if not self.callback(section, option, new_value, old_value):
                raise OperationNotPossibleAtRuntimeException
        RawConfigParser.set(self, section, option, new_value)

    def get(self, section, option, literal_eval=True):
        value = RawConfigParser.get(self, section, option) if RawConfigParser.has_option(self, section, option) else None
        if literal_eval:
            try:
                value = ast.literal_eval(value)
            except:
                pass
        return value

    def copy(self):
        copied_config = CallbackConfigParser()
        for section in self.sections():
            copied_config.add_section(section)
            for option, value in self.items(section):
                copied_config.set(section, option, value)
        return copied_config
