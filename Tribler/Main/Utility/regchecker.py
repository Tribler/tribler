# Written by ABC authors
# see LICENSE.txt for license information

########################################################################
# File ABCRegGUI.py v1.0                                               #
# Tool for associate/unassociate torrent file with ABC                 #
########################################################################

import sys
import os

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

DEBUG = False

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
    
    
