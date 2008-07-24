# Written by Fabian van der Werf
# see LICENSE.txt for license information

import ConfigParser

config = ConfigParser.SafeConfigParser()


def buildConfig(usrconfig, default = None):
    if default != None:
        config.readfp(open(default))

    config.read([usrconfig])


def setOption(section, option, value):
    if not config.has_section(section):
        config.add_section(section)
    
    config.set(section, option, value)

def getOption(section, option):
    try:
        return config.get(section, option)
    except:
        return None
