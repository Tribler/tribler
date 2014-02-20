# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import wx
import sys
import os
import logging

from traceback import print_exc
from cStringIO import StringIO

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.version import version_id, commit_id, build_date
from ConfigParser import RawConfigParser

#
#
# Class: Lang
#
# Keep track of language strings.
#
# Lookups occur in the following order:
# 1. See if the string is in user.lang
# 2. See if the string is in the local language file
# 3. See if the string is in english.lang
#
#


class Lang:

    def __init__(self, utility):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.utility = utility

        filename = self.utility.read_config('language_file')
        langpath = os.path.join(self.utility.getPath(), LIBRARYNAME, "Lang")

        self._logger.info("Setting up languages\n")
        self._logger.info("Language file: %s %s", langpath, filename)

        self.default_section = "ABC/language"

        # Set up user language file (stored in user's config directory)
        self.user_lang = RawConfigParser()
        self.user_lang.read(os.path.join(self.utility.getConfigPath(), 'user.lang'))

        # Set up local language file
        self.local_lang_filename = None
        self.local_lang = None
        local_filepath = os.path.join(langpath, filename)

        if filename != 'english.lang' and existsAndIsReadable(local_filepath):
            self.local_lang_filename = filename
            # Modified
            self.local_lang = wx.FileConfig(localFilename=local_filepath)
            self.local_lang.SetPath(self.default_section)
            # self.local_lang = RawConfigParser()
            # self.local_lang.read(local_filepath)

        # Set up english language file
        english_filepath = os.path.join(langpath, 'english.lang')
        self.english_lang = RawConfigParser()
        self.english_lang.read(english_filepath) if existsAndIsReadable(english_filepath) else None

        self.cache = {}

        self.langwarning = False

    # Retrieve a text string
    def get(self, label, tryuser=True, trylocal=True, tryenglish=True, giveerror=True):
        if tryuser and trylocal and tryenglish:
            tryall = True
        else:
            tryall = False

        if tryall and label in self.cache:
            return self.expandEnter(self.cache[label])

        if (label == 'version'):
            return version_id
        if (label == 'build'):
            return commit_id
        if (label == 'build_date'):
            return build_date
        # see if it exists in 'user.lang'
        if tryuser:
            text, found = self.getFromLanguage(label, self.user_lang)
            if found:
                if tryall:
                    self.cache[label] = text
                return self.expandEnter(text)

        # see if it exists in local language
        if trylocal and self.local_lang is not None:
            text, found = self.getFromLanguage(label, self.local_lang, giveerror=True)
            if found:
                if tryall:
                    self.cache[label] = text
                return self.expandEnter(text)

        # see if it exists in 'english.lang'
        if tryenglish:
            text, found = self.getFromLanguage(label, self.english_lang)
            if found:
                if tryall:
                    self.cache[label] = text
                return self.expandEnter(text)

        # if we get to this point, we weren't able to read anything
        if giveerror:
            self._logger.info("Language file: Got an error finding: %s", label)
            self.error(label)
        return ""

    def expandEnter(self, text):
        text = text.replace("\\r", "\n")
        text = text.replace("\\n", "\n")
        return text

    def getFromLanguage(self, label, langfile, giveerror=False):
        try:
            if langfile is not None:
                if langfile.has_option(self.default_section, label):
                    return self.getSingleline(label, langfile), True
                if langfile.has_option(self.default_section, label + "_line1"):
                    return self.getMultiline(label, langfile), True

                if giveerror:
                    self.error(label, silent=True)
        except:
            fileused = ""
            langfilenames = {"user.lang": self.user_lang,
                            self.local_lang_filename: self.local_lang,
                            "english.lang": self.english_lang}
            for name in langfilenames:
                if langfilenames[name] == langfile:
                    fileused = name
                    break
            sys.stderr.write("Error reading language file: (" + fileused + "), label: (" + label + ")\n")
            data = StringIO()
            print_exc(file=data)
            sys.stderr.write(data.getvalue())

        return "", False

    def getSingleline(self, label, langfile):
        return langfile.get(self.default_section, label).strip("\"")

    def getMultiline(self, label, langfile):
        i = 1
        text = ""
        while (langfile.has_option(self.default_section, label + "_line" + str(i))):
            if (i != 1):
                text += "\n"
            text += langfile.get(self.default_section, label + "_line" + str(i)).strip("\"")
            i += 1
        if not text:
            sys.stdout.write("Language file: Got an error reading multiline string\n")
            self.error(label)
        return text

    def error(self, label, silent=False):
        # Display a warning once that the language file doesn't contain all the values
        if (not self.langwarning):
            self.langwarning = True
            error_title = self.get('error')
            error_text = self.get('errorlanguagefile')
            if (error_text == ""):
                error_text = "Your language file is missing at least one string.\nPlease check to see if an updated version is available."
            # Check to see if the frame has been created yet
            if not silent and hasattr(self.utility, 'frame'):
                # For the moment don't do anything if we can't display the error dialog
                dlg = wx.MessageDialog(None, error_text, error_title, wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
        sys.stderr.write("\nError reading language file!\n")
        sys.stderr.write("  Cannot find value for variable: " + label + "\n")


def existsAndIsReadable(filename):
    return os.access(filename, os.F_OK) and os.access(filename, os.R_OK)
