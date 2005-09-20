import os
import sys
import wx

from string import lower
from traceback import print_exc
from cStringIO import StringIO
from ConfigParser import ConfigParser, MissingSectionHeaderError, NoSectionError

class ConfigReader(ConfigParser):
    def __init__(self, filename, section, defaults = {}):
#        if defaults is None:
#            ConfigParser.__init__(self)
#        else:
#            ConfigParser.__init__(self, defaults)
        ConfigParser.__init__(self)
        self.defaults = defaults

        self.filename = filename
        self.section = section
        
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
        
    def Read(self, param, type = "string", section = None):
        if section is None:
            section = self.section
            
        if param is None or param == "":
            return ""

        defaults = { "string"  : "",
                     "int"     : 0,
                     "float"   : 0.0,
                     "boolean" : False }
                     
        value = defaults[type]
            
        try:
            value = self.get(section, param)
            value = value.strip("\"")
            value = value.strip("'")

#            if self.has_option(section, param):
#                value = self.get(section, param)
#                value = value.strip("\"")
#                value = value.strip("'")
#            else:
#                param = lower(param)
#                if self.defaults.has_key(param):
#                    value = self.defaults[param]
        except:
            param = lower(param)
            if self.defaults.has_key(param):
                value = self.defaults[param]
#            sys.stderr.write("Error while reading parameter: (" + str(param) + ")\n")
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass
            
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
        except:
            value = defaults[type]
           
        return value
        
    def Exists(self, param, section = None):
        if section is None:
            section = self.section
            
        return self.has_option(section, param)
        
    def Write(self, param, value, type = "string", section = None):
        if section is None:
            section = self.section
            
        if param is None or param == "":            
            return False
        
        param = lower(param)
            
        if not self.has_section(section):
            self.add_section(section)
               
        if type == "boolean":
            if value:
                text = "1"
            else:
                text = "0"
        else:
            text = str(value)

        while True:
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