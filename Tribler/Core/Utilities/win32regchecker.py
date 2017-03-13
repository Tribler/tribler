# Written by ABC authors and Arno Bakker
# see LICENSE for license information

import sys
import logging

if sys.platform == 'win32':
    import _winreg

    # short for PyHKEY from "_winreg" module
    HKCR = _winreg.HKEY_CLASSES_ROOT
else:
    HKCR = 0

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
