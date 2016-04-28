# Written by Egbert Bouman
# see LICENSE.txt for license information

import ast
import codecs
from ConfigParser import DEFAULTSECT, RawConfigParser
from threading import RLock

from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException


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
        with codecs.open(filename, 'rb', encoding) as fp:
            self.readfp(fp)

    def set(self, section, option, new_value):
        with self.lock:
            if self.callback and self.has_section(section) and self.has_option(section, option):
                old_value = self.get(section, option)
                if not self.callback(section, option, new_value, old_value):
                    raise OperationNotPossibleAtRuntimeException
            RawConfigParser.set(self, section, option, new_value)

    def get(self, section, option, literal_eval=True):
        value = RawConfigParser.get(self, section, option) if RawConfigParser.has_option(
            self, section, option) else None
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
                fp.write(u"[%s]\n" % DEFAULTSECT)
                for (key, value) in self._defaults.items():
                    fp.write(u"%s = %s\n" % (key, unicode(value).replace(u'\n', u'\n\t')))
                fp.write(u"\n")
            for section in self._sections:
                fp.write(u"[%s]\n" % section)
                for (key, value) in self._sections[section].items():
                    if key != u"__name__":
                        fp.write(u"%s = %s\n" % (key, unicode(value).replace(u'\n', u'\n\t')))
                fp.write(u"\n")

    @staticmethod
    def get_literal_value(value):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value

    def get_config_as_json(self):
        json_dict = {}
        for section in self.sections():
            json_dict[section] = {}
            for option, value in self.items(section):
                json_dict[section][option] = CallbackConfigParser.get_literal_value(value)
        return json_dict
