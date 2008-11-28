# Written by ABC authors
# see LICENSE.txt for license information

import sys
import wx
import os
from traceback import print_stack

from cStringIO import StringIO

from ConfigParser import ConfigParser, MissingSectionHeaderError, NoSectionError, ParsingError, DEFAULTSECT

from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.defaults import dldefaults,DEFAULTPORT

# TODO: remove these defaults, config doesn't work this way with Tribler Core.
bt1_defaults = []
for k,v in dldefaults.iteritems():
    bt1_defaults.append((k,v,"See triblerAPI"))

DEBUG = False

################################################################
#
# Class: ConfigReader
#
# Extension of ConfigParser that supports various types of
# config values.  Values are converted to strings when writing
# and back into their respective types when reading.
#
################################################################
class ConfigReader(ConfigParser):
    def __init__(self, filename, section, defaults = None):
        if defaults is None:
            defaults = {}
            
        ConfigParser.__init__(self)
        self.defaults = defaults

        self.defaultvalues = { "string"  : "",
                               "int"     : 0,
                               "float"   : 0.0,
                               "boolean" : False,
                               "color"   : wx.Colour(0, 0, 0),
                               "bencode-list" : [],
                               "bencode-string": "",
                               "bencode-fontinfo": {'name': None,
                                                    'size': None,
                                                    'style': None,
                                                    'weight': None }
                              }

        self.filename = filename
        self.section = section
        
        # If the directory for this file doesn't exist,
        # try creating it now
        dirname = os.path.dirname(self.filename)
        if not os.access(dirname, os.F_OK):
            os.makedirs(dirname)

        # Arno: Apparently port 6881 is poisoned because ISPs have blocked it.
        # A random port does not work well with Buddycast so, pick a random, fixed one
        if filename.endswith('abc.conf') and not os.access(filename, os.F_OK):
            defaults['minport'] = str(DEFAULTPORT)
        
        try:
            self.read(self.filename)
        except MissingSectionHeaderError:
            # Old file didn't have the section header
            # (add it in manually)
            oldfile = open(self.filename, "r")
            oldconfig = oldfile.readlines()
            oldfile.close()

            newfile = open(self.filename, "w")
            newfile.write("[" + self.section + "]\n")
            newfile.writelines(oldconfig)
            newfile.close()
            
            self.read(self.filename)
        except ParsingError:
            # A more severe exception occured
            # Try to do whatever is possible to repair
            #
            # If this fails, then there's trouble
            self.tryRepair()
            self.read(self.filename)
        
    def testConfig(self, goodconfig, newline, passes = 0):
        if newline:
            testconfig = goodconfig + newline + "\r\n"
            
            # Write out to a StringIO object
            newfile = StringIO(testconfig)
            try:
                testparser = ConfigParser()
                testparser.readfp(newfile)
                
                # Line looks ok, add it to the config file
                return testconfig
            except MissingSectionHeaderError:
                if passes > 0:
                    # Something is odd here... just return the version that works
                    return goodconfig
                else:
                    return self.testConfig(goodconfig + "[" + self.section + "]\n", newline, passes = 1)
            except ParsingError:
                # Ignore the line, don't add it to the config file
                return goodconfig
    
    # Try to repair a damaged config file
    # (i.e.: one w/ parsing errors, etc.)
    def tryRepair(self):
        oldconfig = ""
        
        try:
            oldfile = open(self.filename, "r")
            oldconfig = oldfile.readlines()
            oldfile.close()
        except:
            # Can't read the original file at all
            #
            # try to write a blank file with just the section header
            newfile = open(self.filename, "w")
            newfile.write("[" + self.section + "]\n")
            newfile.close()
            return
            
        goodconfig = ""
        
        for line in oldconfig:
            # Strip off any leading or trailing spaces
            newline = line.strip()

            # If the line looks ok, try writing it
            goodconfig = self.testConfig(goodconfig, newline)

        newfile = open(self.filename, "w")
        newfile.writelines(goodconfig)
        newfile.close()
            
    def setSection(self, section):
        self.section = section

    def ValueToString(self, value, typex):
        if typex == "boolean":
            if value:
                text = "1"
            else:
                text = "0"
        elif typex == "color":
            red = str(value.Red())
            while len(red) < 3:
                red = "0" + red

            green = str(value.Green())            
            while len(green) < 3:
                green = "0" + green
                
            blue = str(value.Blue())            
            while len(blue) < 3:
                blue = "0" + blue

            text = str(red) + str(green) + str(blue)
        elif typex.startswith("bencode"):
            text = bencode(value)
        else:
            if type(value) is unicode:
                text = value
            else:
                text = str(value)
        
        return text

    def StringToValue(self, value, type):
        # Assume that the value is already in the proper form
        # if it's not a string
        # (the case for some defaults)
        if value is not None:
            if not isinstance(value, unicode) and not isinstance(value, str):
                return value

        try:
            if type == "boolean":
                if value == "1":
                    value = True
                else:
                    value = False
            elif type == "int":
                value = int(value)
            elif type == "float":
                value = float(value)
            elif type == "color":
                red = int(value[0:3])
                green = int(value[3:6])
                blue = int(value[6:9])
                value = wx.Colour(red, green, blue)
            elif type.startswith("bencode"):
                value = bdecode(value)
        except:           
            value = None
            
        if value is None:
            value = self.defaultvalues[type]
        
        return value

    def ReadDefault(self, param, type = "string", section = None):
        if section is None:
            section = self.section

        if param is None or param == "":
            return ""

        param = param.lower()
        value = self.defaults.get(param, None)
            
        value = self.StringToValue(value, type)
            
        return value
        
    def Read(self, param, type = "string", section = None):
        if section is None:
            section = self.section
            
        if DEBUG:
            print >>sys.stderr,"ConfigReader: Read(",param,"type",type,"section",section
            
        if param is None or param == "":
            return ""

#        value = None

        try:
            value = self.get(section, param)
            value = value.strip("\"")
#            value = value.strip("'")
        except:
            param = param.lower()
            value = self.defaults.get(param, None)
            if DEBUG:
                sys.stderr.write("ConfigReader: Error while reading parameter: (" + str(param) + ")\n")
            # Arno, 2007-03-21: The ABCOptions dialog tries to read config values
            # via this mechanism. However, that doesn't take into account the
            # values from BitTornado/download_bt1.py defaults. I added that.
            if value is None:
                if not DEBUG:
                    sys.stderr.write("ConfigReader: Error while reading parameter, no def: (" + str(param) + ")\n")
                    print_stack()
                    
                for k,v,d in bt1_defaults:
                    if k == param:
                        value = v
                        break
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

        if DEBUG:
            print >>sys.stderr,"ConfigReader: Read",param,type,section,"got",value

        value = self.StringToValue(value, type)
           
        return value
        
    def Exists(self, param, section = None):
        if section is None:
            section = self.section
            
        return self.has_option(section, param)
        
    def Items(self, section = None):
        if section is None:
            section = self.section
        
        try:
            items = self.items(section)
            for i in range(len(items)):
                (key, value) = items[i]
                value = value.strip("\"")
#                value = value.strip("'")
                items[i] = (key, value)
            return items
        except:
            self.add_section(section)
        return []

    def GetOptions(self, section = None):
        if section is None:
            section = self.section
        try:
            options = self.options(section)
        except NoSectionError:
            options = []
        return options

    def Write(self, param, value, type = "string", section = None):
        if section is None:
            section = self.section
            
        if param is None or param == "":            
            return False
        
        param = param.lower()
            
        if not self.has_section(section):
            self.add_section(section)
               
        text = self.ValueToString(value, type)

        while 1:
            try:
                oldtext = self.Read(param)
                
                self.set(section, param, text)
    
                # Return True if we actually changed something            
                if oldtext != text:
                    return True
                
                break
            except NoSectionError:
                self.add_section(section)
            except:
#                sys.stderr.write("Error while writing parameter: (" + str(param) + ") with value: (" + str(text) + ")\n")
#                data = StringIO()
#                print_exc(file = data)
#                sys.stderr.write(data.getvalue())
                break
        
        return False
    
    def DeleteEntry(self, param, section = None):
        if section is None:
            section = self.section
               
        try:
            return self.remove_option(section, param)
        except:
            return False
        
    def DeleteGroup(self, section = None):
        if section is None:
            section = self.section

        try:
            return self.remove_section(section)
        except:
            return False
        
    def Flush(self):        
        self.write(open(self.filename, "w"))

    def _read(self, fp, fpname):
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        firstline = True            
        while True:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            if firstline:
                # Skip BOM
                if line[:3] == '\xef\xbb\xbf':
                    line = line[3:]
                    self.encoding = 'utf_8'
                else:
                    self.encoding = sys.getfilesystemencoding()
                firstline = False
            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname] = "%s\n%s" % (cursect[optname], value.decode(self.encoding))
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = {'__name__': sectname}
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self.OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi in ('=', ':') and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos-1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        optname = self.optionxform(optname.rstrip())
                        try:
                            _opt = optval.decode(self.encoding)
                        except UnicodeDecodeError:
                            self.encoding = sys.getfilesystemencoding()
                            _opt = optval.decode(self.encoding)
                        cursect[optname] = _opt
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e
        
    def write(self, fp):
        fp.writelines('\xef\xbb\xbf')
        if self._defaults:
            fp.write("[%s]\n" % DEFAULTSECT)
            for (key, value) in self._defaults.items():
                if type(value) is not str and type(value) is not unicode:
                    value = str(value)
                fp.write((key + " = " + value + "\n").encode('utf_8'))
            fp.write("\n")
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key != "__name__":
                    if type(value) is not str and type(value) is not unicode:
                        value = str(value)
                    try:
                        fp.write((key + " = " + value + "\n").encode('utf_8'))
                    # for unicode bencod-list items (already UTF-8 encoded)
                    except UnicodeDecodeError:
                        fp.write((key + " = " + value + "\n"))
            fp.write("\n")






