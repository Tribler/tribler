# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements marshaling and unmarshalling
between string values in and python objects, in
accordance with the UPnP specification.
"""

import types
import exceptions


class MarshalError(exceptions.Exception):

    """
    Error associated with marshalling and unmarshalling.
    """
    pass

#
# LOADS
#


def loads(type_, data):
    """Load string data and return value of given type."""
    if type_ == int:
        return int(data)
    elif type_ in str:
        return str(data)
    elif type_ == bool:
        if data in ['1', 'true', 'True', 'yes']:
            return True
        elif data in ['0', 'false', 'False', 'no']:
            return False
        else:
            raise MarshalError("Loads: Boolean failed %s" % data)
    else:
        raise MarshalError("Loads: Unsupported Type %s" % type_)


def loads_data_by_upnp_type(upnp_type_string, data_string):
    """Loads string data into a python value given a string definition
    of the UPnP data type.
    """
    if upnp_type_string == 'boolean':
        if data_string in ['1', 'true', 'True', 'yes']:
            return True
        elif data_string in ['0', 'false', 'False', 'no']:
            return False
    elif upnp_type_string == 'int':
        return int(data_string)
    elif upnp_type_string == 'string':
        return str(data_string)
    elif upnp_type_string == 'ui1':
        # Unsigned 1 byte integer
        return int(data_string) & 0xFF
    elif upnp_type_string == 'ui2':
        # Unsigned 2 byte integer
        return int(data_string) & 0xFFFF
    elif upnp_type_string == 'ui4':
        # Unsigned 1 byte integer
        return int(data_string) & 0xFFFFFFFF
    else:
        raise MarshalError("Loads: Unsupported Type %s" % upnp_type_string)


#
# DUMPS
#

def dumps_by_upnp_type(upnp_type_string, value):
    """Dumps python value into a string according to upnp_type_string."""
    if isinstance(value, bool) and upnp_type_string == "boolean":
        return u'1' if value == True else u'0'
    elif isinstance(value, str) and upnp_type_string == 'string':
        return unicode("<![CDATA[%s]]>" % value)
    elif isinstance(value, int) and upnp_type_string == 'ui1':
        return unicode(value & 0xFF)
    elif isinstance(value, int) and upnp_type_string == 'ui2':
        return unicode(value & 0xFFFF)
    elif isinstance(value, int) and upnp_type_string == 'ui4':
        return unicode(value & 0xFFFFFFFF)
    elif isinstance(value, int) and upnp_type_string == 'int':
        return unicode(value)
    else:
        msg = "Dumps: Unsupported Type %s" % str(value)
        raise MarshalError(msg)


def dumps(value):
    """Dump typed value to unicode string"""
    if isinstance(value, bool):
        return u'1' if value == True else u'0'
    elif isinstance(value, str):
        return unicode("<![CDATA[%s]]>" % value)
    elif isinstance(value, int):
        return unicode(value)
    else:
        msg = "Dumps: Unsupported Type %s" % str(value)
        raise MarshalError(msg)

#
# DATATYPES
#


def dumps_data_type(python_type):
    """Converts a python type object to a string,
    according to UPnP specification."""
    if python_type == bool:
        return u'boolean'
    elif python_type == int:
        return u'int'
    elif python_type == bytes:
        return u'string'
    else:
        msg = "Dumps Datatype: Unsupported Type %s" % str(python_type)
        raise MarshalError(msg)


def loads_python_type(type_string):
    """Converts a UPnP variable type string to a python type object."""
    if type_string == 'boolean':
        return bool
    elif type_string in ['int', 'ui1', 'ui2', 'ui4']:
        return int
    elif type_string == u'string':
        return bytes
    else:
        msg = "Loads Datatype: Unsupported Type %s" % type_string
        raise MarshalError(msg)


#
# MAIN
#
if __name__ == '__main__':
    pass
