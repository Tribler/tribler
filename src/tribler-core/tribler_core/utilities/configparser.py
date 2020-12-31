"""
A configparser.

Author(s): Egbert Bouman
"""
import ast
import codecs
from configparser import DEFAULTSECT, RawConfigParser
from io import StringIO
from threading import RLock

from tribler_core.exceptions import OperationNotPossibleAtRuntimeException


class CallbackConfigParser(RawConfigParser):

    def __init__(self, *args, **kwargs):
        RawConfigParser.__init__(self, *args, **kwargs)
        self.filename = None
        self.callback = None
        self.lock = RLock()

    def set_callback(self, callback):
        with self.lock:
            self.callback = callback

    def read_file(self, filename, encoding='utf-8'):
        self.filename = filename
        # We load the file in-memory, which significantly helps performance in case we have big files
        # (e.g. when loading resumedata). Please do not remove.
        with codecs.open(filename, 'rb', encoding) as fp:
            buff = fp.read()
        self._read(StringIO(buff), None)

    def set(self, section, option, new_value):
        with self.lock:
            if self.callback and self.has_section(section) and self.has_option(section, option):
                old_value = self.get(section, option)
                if not self.callback(section, option, new_value, old_value):
                    raise OperationNotPossibleAtRuntimeException
            RawConfigParser.set(self, section, option, new_value)

    def get(self, section, option, literal_eval=True):
        value = RawConfigParser.get(self, section, option) if \
            RawConfigParser.has_option(self, section, option) else None
        if literal_eval:
            return CallbackConfigParser.get_literal_value(value)
        return value

    def copy(self):
        with self.lock:
            copied_config = CallbackConfigParser()
            for section in self.sections():
                copied_config.add_section(section)
                for option, value in self.items(section):
                    copied_config.set(section, option, value)
            return copied_config

    def write_file(self, filename=None, encoding='utf-8'):
        if not filename:
            filename = self.filename

        with codecs.open(filename, 'wb', encoding) as fp:
            self.write(fp)

    def write(self, fp):
        with self.lock:
            if self._defaults:
                fp.write(f"[{DEFAULTSECT}]\n")
                for (key, value) in self._defaults.items():
                    fp.write("{} = {}\n".format(key, str(value).replace('\n', '\n\t')))
                fp.write("\n")
            for section in self._sections:
                fp.write(f"[{section}]\n")
                for (key, value) in self._sections[section].items():
                    if key != "__name__":
                        fp.write("{} = {}\n".format(key, str(value).replace('\n', '\n\t')))
                fp.write("\n")

    @staticmethod
    def get_literal_value(value):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError, TypeError):
            return value

    def get_config_as_json(self):
        json_dict = {}
        for section in self.sections():
            json_dict[section] = {}
            for option, value in self.items(section):
                json_dict[section][option] = CallbackConfigParser.get_literal_value(value)
        return json_dict
