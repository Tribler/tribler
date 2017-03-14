"""
This file should contain code for hacks needed to work around bugs in non-tribler code.
"""
import sys

# Needed because of python-cryptography doing weird stuff when scanning for backends.
# Should be removed as soon as https://github.com/pyca/cryptography/issues/2039 gets closed.
# This code is based on https://github.com/pyca/cryptography/issues/2039#issuecomment-115432291
# with some modifications so it only gets called when running an installer version of Tribler on windows.
# TODO(emilon): remove this when Tribler gets migrated to python 3.
if sys.platform == "win32":
    import ctypes

    # WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!
    #
    # There's a copy of the following two functions in tribler_exe.py due to this file
    # depending on them to be able to update the PYTHONPATH so it can import anything
    # else and this file being deleted when py2exe freezes it. So please, if you
    # modify them, update their twin brothers too!
    #
    # WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING! WARNING!

    # From: https://measureofchaos.wordpress.com/2011/03/04/python-on-windows-unicode-environment-variables/
    def get_environment_variable(name):
        """Get the unicode version of the value of an environment variable
        """
        name = unicode(name)
        n = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)
        if n == 0:
            return None
        buf = ctypes.create_unicode_buffer(u'\0' * n)
        ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, n)
        return buf.value

    def set_environment_variable(name, value):
        """Unicode compatible environment variable setter
        """
        if ctypes.windll.kernel32.SetEnvironmentVariableW(name, value) == 0:
            raise RuntimeError("Failed to set env. variable '%s' to '%s" %
                               (repr(name), repr(value)))

#
# hacks.py ends here
