# Written by ABC authors and Arno Bakker
# see LICENSE.txt for license information

import sys
import logging

if sys.platform == 'win32':
    import _winreg

    # short for PyHKEY from "_winreg" module
    HKCR = _winreg.HKEY_CLASSES_ROOT
    HKLM = _winreg.HKEY_LOCAL_MACHINE
    HKCU = _winreg.HKEY_CURRENT_USER
else:
    HKCR = 0
    HKLM = 1
    HKCU = 2

logger = logging.getLogger(__name__)


class Win32RegChecker:

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def readRootKey(self, key_name, value_name=""):
        return self.readKey(HKCR, key_name, value_name)

    def readKey(self, hkey, key_name, value_name=""):
        if sys.platform != 'win32':
            return None

        try:
            # test that shell/open association with ABC exist
            self._logger.debug("win32regcheck: Opening %s %s", key_name, value_name)
            full_key = _winreg.OpenKey(hkey, key_name, 0, _winreg.KEY_READ)

            self._logger.debug("win32regcheck: Open returned %s", full_key)

            value_data, value_type = _winreg.QueryValueEx(full_key, value_name)
            self._logger.debug("win32regcheck: Read %s %s", value_data, value_type)
            _winreg.CloseKey(full_key)

            return value_data
        except Exception as ex:
            self._logger.exception("hkey: %s, key_name: %s, value_name: %s", hkey, key_name, value_name)
            # error, test failed, key don't exist
            # (could also indicate a unicode error)
            return None

    def readKeyRecursively(self, hkey, key_name, value_name=""):
        if (sys.platform != 'win32'):
            return None

        lasthkey = hkey
        try:
            toclose = []
            keyparts = key_name.split('\\')
            self._logger.info("win32regcheck: keyparts %s", keyparts)
            for keypart in keyparts:
                if keypart == '':
                    continue
                self._logger.debug("win32regcheck: Opening %s", keypart)
                full_key = _winreg.OpenKey(lasthkey, keypart, 0, _winreg.KEY_READ)
                lasthkey = full_key
                toclose.append(full_key)

            self._logger.debug("win32regcheck: Open returned %s", full_key)

            value_data, value_type = _winreg.QueryValueEx(full_key, value_name)
            self._logger.debug("win32regcheck: Read %s %s", value_data, value_type)
            for hkey in toclose:
                _winreg.CloseKey(hkey)

            return value_data
        except Exception as ex:
            self._logger.exception("hkey: %s, key_name: %s, value_name: %s", hkey, key_name, value_name)
            # error, test failed, key don't exist
            # (could also indicate a unicode error)
            return None

    def writeKey(self, hkey, key_name, value_name, value_data, value_type):
        try:
            # kreate desired key in Windows register
            full_key = _winreg.CreateKey(hkey, key_name)
        except EnvironmentError:
            return False
        # set desired value in created Windows register key
        _winreg.SetValueEx(full_key, value_name, 0, value_type, value_data)
        # close Windows register key
        _winreg.CloseKey(full_key)

        return True


if __name__ == "__main__":
    w = Win32RegChecker()
    winfiletype = w.readRootKey(".wmv")
    playkey = winfiletype + "\shell\play\command"
    urlplay = w.readRootKey(playkey)
    logger.info(repr(urlplay))
    openkey = winfiletype + "\shell\open\command"
    urlopen = w.readRootKey(openkey)
    logger.info(repr(urlopen))
