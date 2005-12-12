import sys
import wx
import os

from ConfigParser import ConfigParser, MissingSectionHeaderError, NoSectionError

from BitTornado.bencode import bencode, bdecode

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
            
    def setSection(self, section):
        self.section = section

    def ValueToString(self, value, type):
        if type == "boolean":
            if value:
                text = "1"
            else:
                text = "0"
        elif type == "color":
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
        elif type.startswith("bencode"):
            text = bencode(value)
        else:
            text = str(value)
        
        return text

    def StringToValue(self, value, type):
        # Assume that the value is already in the proper form
        # if it's not a string
        # (the case for some defaults)
        if value is not None and not isinstance(value, str):
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
#            sys.stderr.write("Error while reading parameter: (" + str(param) + ")\n")
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

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