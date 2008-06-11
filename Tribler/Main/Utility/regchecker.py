########################################################################
# File ABCRegGUI.py v1.0                                               #
# Tool for associate/unassociate torrent file with ABC                 #
########################################################################

import sys
import os
from traceback import print_exc

if (sys.platform == 'win32'):
    import _winreg

    # short for PyHKEY from "_winreg" module
    HKCR = _winreg.HKEY_CLASSES_ROOT
    HKLM = _winreg.HKEY_LOCAL_MACHINE
    HKCU = _winreg.HKEY_CURRENT_USER
else:
    HKCR = 0
    HKLM = 1
    HKCU = 2

DEBUG = True

################################################################
#
# Class: RegChecker
#
# Used to check whether or not ABC is associated as the
# default BitTorrent application
#
################################################################
class RegChecker:
    def __init__(self, utility):
        self.utility = utility
        
        if (sys.platform != 'win32'):
            return
        
        abcpath = os.path.join(self.utility.getPath(), "tribler.exe")
#        abcpath = os.path.normcase(abcpath)
        iconpath = os.path.join(self.utility.getPath(), "torrenticon.ico")
    
        # Arno: 2007-06-18: Assuming no concurrency on TRIBLER_TORRENT_EXT
        # tuple (array) with key to register
        self.reg_data = [ (r".torrent", "", "bittorrent", _winreg.REG_SZ), 
                          (r".torrent", "Content Type", r"application/x-bittorrent", _winreg.REG_SZ), 
                          (r"MIME\Database\Content Type\application/x-bittorrent", "Extension", ".torrent", _winreg.REG_SZ), 
                          (r"bittorrent", "", "TORRENT File", _winreg.REG_SZ), 
                          (r"bittorrent\DefaultIcon", "", iconpath,_winreg.REG_SZ),
                          (r"bittorrent", "EditFlags", chr(0)+chr(0)+chr(1)+chr(0), _winreg.REG_BINARY), 
                          (r"bittorrent\shell", "", "open", _winreg.REG_SZ), 
                          (r"bittorrent\shell\open\command", "", "\"" + abcpath + "\" \"%1\"", _winreg.REG_SZ)]
        self.reg_data_delete = [ (r"bittorrent\shell\open\ddeexec") ]
    
        # tuple (array) with key to delete    
        self.unreg_data = [ (r"bittorrent\shell\open\command"), 
                            (r"bittorrent\shell\open"), 
                            (r"bittorrent\shell"), 
                            (r"bittorrent"), 
                            (r"MIME\Database\Content Type\application/x-bittorrent"), 
                            (r".torrent") ]

    # function that test Windows register for key & value exist
    def testRegistry(self):
        if (sys.platform != 'win32'):
            return False
            
        key_name, value_name, value_data, value_type = self.reg_data[7]

        try:
            # test that shell/open association with ABC exist
            _abc_key = _winreg.OpenKey(HKCR, key_name, 0, _winreg.KEY_READ)
            _value_data, _value_type = _winreg.QueryValueEx(_abc_key, value_name)
            _winreg.CloseKey(_abc_key)
                    
            _value_data = os.path.normcase(_value_data)
            value_data = os.path.normcase(value_data)
            
            if _value_data != value_data:
                # association with ABC don't exist
                return False
        except:
            # error, test failed, key don't exist
            # (could also indicate a unicode error)
            return False
        
        # If ABC is registred, remove keys (ddeexec) that may interfere:
        self.removeKeys(self.reg_data_delete)
            
        return True

    def updateRegistry(self, register = True):
        if (sys.platform != 'win32'):
            return False

        if register:
            return self.registerABC()
        else:
            return self.unregisterABC()
            
    # Add a set of keys to the registry
    def addKeys(self, keys):
        for _key_name, _value_name, _value_data, _value_type in keys:
            try:
                # kreate desired key in Windows register
                _abc_key = _winreg.CreateKey(HKCR, _key_name)
            except EnvironmentError:
                return False;
            # set desired value in created Windows register key
            _winreg.SetValueEx(_abc_key, _value_name, 0, _value_type, _value_data)
            # close Windows register key
            _winreg.CloseKey(_abc_key)
            
        return True
    
    # Remove a set of keys from the registry    
    def removeKeys(self, keys):
        for _key_name in keys:
            try:
                # delete desired Windows register key
                _winreg.DeleteKey(HKCR, _key_name)
            except EnvironmentError:
                return False;

    # function that regitered key in Windows register
    def registerABC(self):
        if (sys.platform != 'win32'):
            return False

        # if ABC is already registered,
        # we don't need to do anything
        if self.testRegistry():
            return

        # "for" loop to get variable from tuple
        success = self.addKeys(self.reg_data)
        if not success:
            return False

        # delete ddeexec key
        success = self.removeKeys(self.reg_data_delete)
        if not success:
            return False

        return True

    # function that delete key in Windows register
    def unregisterABC(self):
        if (sys.platform != 'win32'):
            return False
            
        # if ABC isn't already registered,
        # we don't need to do anything
        if not self.testRegistry():
            return

        # get variable for key deletion from tuple
        success = self.removeKeys(self.unreg_data)
        if not success:
            return False

        return True
    
    
class Win32RegChecker:
    def __init__(self):
        pass

    def readRootKey(self,key_name,value_name=""):
        return self.readKey(HKCR,key_name,value_name)
        
    def readKey(self,hkey,key_name,value_name=""):
        if (sys.platform != 'win32'):
            return None
            
        try:
            # test that shell/open association with ABC exist
            if DEBUG:
                print >>sys.stderr,"win32regcheck: Opening",key_name,value_name
            full_key = _winreg.OpenKey(hkey, key_name, 0, _winreg.KEY_READ)
            
            if DEBUG:
                print >>sys.stderr,"win32regcheck: Open returned",full_key
            
            value_data, value_type = _winreg.QueryValueEx(full_key, value_name)
            if DEBUG:
                print >>sys.stderr,"win32regcheck: Read",value_data,value_type
            _winreg.CloseKey(full_key)
                    
            return value_data
        except:
            print_exc(file=sys.stderr)
            # error, test failed, key don't exist
            # (could also indicate a unicode error)
            return None


    def readKeyRecursively(self,hkey,key_name,value_name=""):
        if (sys.platform != 'win32'):
            return None
            
        lasthkey = hkey
        try:
            toclose = []
            keyparts = key_name.split('\\')
            print >>sys.stderr,"win32regcheck: keyparts",keyparts
            for keypart in keyparts:
                if keypart == '':
                    continue
                if DEBUG:
                    print >>sys.stderr,"win32regcheck: Opening",keypart
                full_key = _winreg.OpenKey(lasthkey, keypart, 0, _winreg.KEY_READ)
                lasthkey = full_key
                toclose.append(full_key)
            
            if DEBUG:
                print >>sys.stderr,"win32regcheck: Open returned",full_key
            
            value_data, value_type = _winreg.QueryValueEx(full_key, value_name)
            if DEBUG:
                print >>sys.stderr,"win32regcheck: Read",value_data,value_type
            for hkey in toclose:
                _winreg.CloseKey(hkey)
                    
            return value_data
        except:
            print_exc()
            # error, test failed, key don't exist
            # (could also indicate a unicode error)
            return None


    def writeKey(self,hkey,key_name,value_name,value_data,value_type):
        try:
            # kreate desired key in Windows register
            full_key = _winreg.CreateKey(hkey, key_name)
        except EnvironmentError:
            return False;
        # set desired value in created Windows register key
        _winreg.SetValueEx(full_key, value_name, 0, value_type, value_data)
        # close Windows register key
        _winreg.CloseKey(full_key)
            
        return True



if __name__ == "__main__":
    w = Win32RegChecker()
    winfiletype = w.readRootKey(".wmv")
    playkey = winfiletype+"\shell\play\command"
    urlplay = w.readRootKey(playkey)
    print urlplay
    openkey = winfiletype+"\shell\open\command"
    urlopen = w.readRootKey(openkey)
    print urlopen
