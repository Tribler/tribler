#!/usr/bin/python
# Written by Boudewijn Schoon
# see LICENSE.txt for license information

"""
Use the garbage collector to monitor memory usage
"""

from types import *
import gc
import inspect
import sys
import thread
import time


def _get_default_footprint(obj, depth):
    return 4


def _get_int_footprint(obj, depth):
    return 4


def _get_float_footprint(obj, depth):
    return 8


def _get_string_footprint(obj, depth):
    return len(obj)


def _get_unicode_footprint(obj, depth):
    return 2 * len(obj)


def _get_tuple_footprint(obj, depth):
    if depth == 0:
        return 4 + 4 * len(obj)
    else:
        return 4 + 4 * len(obj) + sum(map(lambda obj: get_memory_footprint(obj, depth), obj))


def _get_list_footprint(obj, depth):
    if depth == 0:
        return 8 + 4 * len(obj)
    else:
        if len(obj) in (2, 3):
            print >> sys.stderr, "Len:", type(obj[0]), type(obj[1])
            print >> sys.stderr, repr(obj)
            return 42
        print >> sys.stderr, "Len:", len(obj)
        return 8 + 4 * len(obj) + sum(map(lambda obj: get_memory_footprint(obj, depth), obj))


def _get_dict_footprint(obj, depth):
    if depth == 0:
        return 32 + 8 * len(obj)
    else:
        return 32 + 8 * len(obj) + sum(map(lambda obj: get_memory_footprint(obj, depth), obj.iterkeys())) + sum(map(lambda obj: get_memory_footprint(obj, depth), obj.itervalues()))

memory_footprint_map = {IntType: _get_int_footprint,
                        FloatType: _get_float_footprint,
                        StringType: _get_float_footprint,
                        UnicodeType: _get_unicode_footprint,
                        TupleType: _get_tuple_footprint,
                        ListType: _get_list_footprint,
                        DictType: _get_dict_footprint}


def get_memory_footprint(obj, depth=100):
    return memory_footprint_map.get(type(obj), _get_default_footprint)(obj, depth - 1)


def _get_default_description(obj):
    return type(obj)


def _get_function_description(obj):
    return "<function '%s' from '%s'>" % (obj.__name__, obj.__module__)


def _get_module_description(obj):
    return str(obj)


def _get_frame_description(obj):
    return "<frame for '%s' from %s:%d >" % (obj.f_code.co_name, obj.f_code.co_filename, obj.f_code.co_firstlineno)

description_map = {FunctionType: _get_function_description,
                   ModuleType: _get_module_description,
                   FrameType: _get_frame_description}


def get_description(obj):
    return description_map.get(type(obj), _get_default_description)(obj)


def get_datetime():
    return time.strftime("%Y/%m/%d %H:%M:%S")


def byte_uint_to_human(i, format="%(value).1f%(unit)s"):
    """Convert a number into a formatted string.

    format: %(value)d%(unit)s
    1           --> 1B
    1024        --> 1KB
    1048576     --> 1MB
    1073741824  --> 1GB

    format: %(value).1f %(unit-long)s
    1           --> 1.0 byte
    2           --> 2.0 bytes

    todo:
    - uint_to_human(1025, format="%(value)d %(unit-long)s") --> '1 kilobytes'
      however, this should result in '1 kilobyte'

    """
    assert type(i) in (int, long)
    assert i >= 0
    assert isinstance(format, str)
    dic = {}
    if i < 1024:
        dic["value"] = i
        dic["unit"] = "B"
        dic["unit-long"] = (i == 1 and "byte" or "bytes")
    elif i < 1048576:
        dic["value"] = i / 1024.0
        dic["unit"] = "KB"
        dic["unit-long"] = (i == 1024 and "kilobyte" or "kilobytes")
    elif i < 1073741824:
        dic["value"] = i / 1048576.0
        dic["unit"] = "MB"
        dic["unit-long"] = (i == 1048576 and "megabyte" or "megabytes")
    else:
        dic["value"] = i / 1073741824.0
        dic["unit"] = "GB"
        dic["unit-long"] = (i == 1073741824 and "gigabyte" or "gigabytes")

    return format % dic


def monitor(delay=10.0, interval=60.0, min_footprint=100000):
    def parallel():
        time.sleep(delay)

        history = [min_footprint]
        while True:
            high_foot = 0
            history = history[-2:]
            low_foot = min(history)
            datetime = get_datetime()
            print >> sys.stderr, "Memory:", datetime, "using minimal footprint:", byte_uint_to_human(low_foot)

            gc.collect()
            for obj in gc.get_objects():
                if type(obj) in (TupleType, ListType, DictType, StringType, UnicodeType):
                    try:
                        footprint = get_memory_footprint(obj)
                    except:
                        print >> sys.stderr, "Memory:", datetime, "unable to get footprint for", get_description(obj)
                    else:
                        if footprint > high_foot:
                            high_foot = footprint
                        if footprint >= low_foot:

                            print >> sys.stderr, "Memory:", datetime, get_description(obj), "footprint:", byte_uint_to_human(footprint)
                            for referrer in gc.get_referrers(obj):
                                print >> sys.stderr, "Memory:", datetime, "REF", get_description(referrer)
                            print >> sys.stderr, "Memory"

            history.append(high_foot)
            time.sleep(interval)

    thread.start_new_thread(parallel, ())


def main():
    """
    Test the memory monitor
    """
    monitor(1.0)
    time.sleep(10)

if __name__ == "__main__":
    main()
