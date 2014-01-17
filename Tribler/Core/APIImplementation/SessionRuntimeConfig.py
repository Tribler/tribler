# Written by Arno Bakker
# Updated by Egbert Bouman
# see LICENSE.txt for license information

from Tribler.Core.SessionConfig import SessionConfigInterface

# 10/02/10 Boudewijn: pylint points out that member variables used in
# SessionRuntimeConfig do not exist.  This is because they are set in
# Tribler.Core.Session which is a subclass of SessionRuntimeConfig.
#
# We disable this error
# pylint: disable-msg=E1101


class SessionRuntimeConfig(SessionConfigInterface):

    """
    Implements the Tribler.Core.API.SessionConfigInterface

    Use these to change the session config at runtime.
    """

    def set_config_callback(self, callback):
        self.sessconfig.set_callback(callback)

    def _execute_with_sesslock(self, f, *args, **kwargs):
        with self.sesslock:
            return f(*args, **kwargs)

    def __getattribute__(self, name):
        attr = SessionConfigInterface.__getattribute__(self, name)
        if name in dir(SessionConfigInterface):
            if name.startswith('get_') or name.startswith('set_'):
                if hasattr(attr, '__call__'):
                    sesslock_func = SessionConfigInterface.__getattribute__(self, '_execute_with_sesslock')
                    return lambda *args, **kwargs: sesslock_func(attr, *args, **kwargs)
        return attr
