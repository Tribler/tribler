# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information
import wx
import sys
import os

from traceback import print_exc, print_stack
from cStringIO import StringIO

from Tribler.__init__ import LIBRARYNAME
from Tribler.Utilities.configreader import ConfigReader
from Tribler.Core.BitTornado.__init__ import version_id

################################################################
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
################################################################
class Lang:
    def __init__(self, utility):
        self.utility = utility
        
        filename = self.utility.config.Read('language_file')
        
        
        langpath = os.path.join(self.utility.getPath(), LIBRARYNAME,  "Lang")
        
        sys.stdout.write("Setting up languages\n")
        sys.stdout.write("Language file: " + str(filename) + "\n")
        
        # Set up user language file (stored in user's config directory)
        self.user_lang = None
        user_filepath = os.path.join(self.utility.getConfigPath(), 'user.lang')
        self.user_lang = ConfigReader(user_filepath, "ABC/language")

        # Set up local language file
        self.local_lang_filename = None
        self.local_lang = None
        local_filepath = os.path.join(langpath, filename)
        
        if filename != 'english.lang' and existsAndIsReadable(local_filepath):
            self.local_lang_filename = filename
            # Modified
            self.local_lang = wx.FileConfig(localFilename = local_filepath)
            self.local_lang.SetPath("ABC/language")
            #self.local_lang = ConfigReader(local_filepath, "ABC/language")
        
        # Set up english language file
        self.english_lang = None
        english_filepath = os.path.join(langpath, 'english.lang')
        if existsAndIsReadable(english_filepath):
            self.english_lang = ConfigReader(english_filepath, "ABC/language")
        
        self.cache = {}
        
        self.langwarning = False
        
    def flush(self):
        if self.user_lang is not None:
            try:
                self.user_lang.DeleteEntry("dummyparam", False)
            except:
                pass
            self.user_lang.Flush()
        self.cache = {}
              
    # Retrieve a text string
    def get(self, label, tryuser = True, trylocal = True, tryenglish = True, giveerror = True):        
        if tryuser and trylocal and tryenglish:
            tryall = True
        else:
            tryall = False
    
        if tryall and label in self.cache:
            return self.expandEnter(self.cache[label])
    
        if (label == 'version'):
            return version_id
        if (label == 'build'):
            return "Build 13622"
        if (label == 'build_date'):
            return "Nov 12, 2009"
        # see if it exists in 'user.lang'
        if tryuser:
            text, found = self.getFromLanguage(label, self.user_lang)
            if found:
                if tryall:
                    self.cache[label] = text
                return self.expandEnter(text)

        # see if it exists in local language
        if trylocal and self.local_lang is not None:
            text, found = self.getFromLanguage(label, self.local_lang, giveerror = True)
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
            sys.stdout.write("Language file: Got an error finding: "+label)
            self.error(label)
        return ""
        
    def expandEnter(self, text):
        text = text.replace("\\r","\n")
        text = text.replace("\\n","\n")
        return text
        
    def getFromLanguage(self, label, langfile, giveerror = False):
        try:
            if langfile is not None:
                if langfile.Exists(label):
                    return self.getSingleline(label, langfile), True
                if langfile.Exists(label + "_line1"):
                    return self.getMultiline(label, langfile), True
                
                if giveerror:
                    self.error(label, silent = True)
        except:
            fileused = ""
            langfilenames = { "user.lang": self.user_lang, 
                              self.local_lang_filename: self.local_lang, 
                              "english.lang": self.english_lang }
            for name in langfilenames:
                if langfilenames[name] == langfile:
                    fileused = name
                    break
            sys.stderr.write("Error reading language file: (" + fileused + "), label: (" + label + ")\n")
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())            
                
        return "", False
        
    def getSingleline(self, label, langfile):
        return langfile.Read(label)
    
    def getMultiline(self, label, langfile):
        i = 1
        text = ""
        while (langfile.Exists(label + "_line" + str(i))):
            if (i != 1):
                text+= "\n"
            text += langfile.Read(label + "_line" + str(i))
            i += 1
        if not text:
            sys.stdout.write("Language file: Got an error reading multiline string\n")
            self.error(label)
        return text
        
    def writeUser(self, label, text):
        change = False
        
        text_user = self.get(label, trylocal = False, tryenglish = False, giveerror = False)
        text_nonuser = self.get(label, tryuser = False, giveerror = False)
               
        user_lang = self.user_lang
        
        # The text string is the default string
        if text == text_nonuser:
            # If there was already a user string, delete it
            # (otherwise, do nothing)
            if text_user != "":
                user_lang.Write("exampleparam", "example value")
                user_lang.DeleteEntry(label)
                change = True
        elif text != text_user:
            # Only need to update if the text string differs
            # from what was already stored
            user_lang.Write(label, text)
            change = True
        
        return change
        
    def error(self, label, silent = False):
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
