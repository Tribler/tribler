from __future__ import absolute_import

from collections import Iterable
import json

from six import string_types

__all__ = ['dumps', 'loads']


def _is_undumpable(obj):
    """
    Check if JSON can dump an object.

    :param obj: the object to check for dumpability
    :return: the string safe version of the object if undumpable, '' otherwise
    """
    try:
        json.dumps(obj)
        return ''
    except UnicodeDecodeError:
        return repr(obj)


def _scan_iterable(obj, context=None):
    """
    Scan an object for dumpable members if iterable or the dumpability of itself, given some context.

    This recurses over the obj if it is iterable.
    Otherwise, it performs an _is_undumpable() check.

    If the object appears to be undumpable, it will extend the return value with its name added to the current context.

    :param obj: the (possibly iterable) object to check for dumpability
    :param context: the context to report the dumpability of this object for
    :return: a list of undumpable objects in context, represented as lists
    """
    if context is None:
        context = []
    out = []
    # First check if we need to recurse into the children of obj.
    # Note that there is one type of object we don't want to step into, which is a string object.
    if not isinstance(obj, string_types) and isinstance(obj, Iterable):
        for sub in obj:
            # If we are iterating over a dict, we are iterating over its keys.
            # 1. We can then give a named trace instead of an anonymous trace
            # 2. We need to check if the key itself is dumpable
            if isinstance(obj, dict):
                undumpable = _is_undumpable(sub)
                if undumpable:
                    # We cant dump the key, output "OBJ_CLASS::KEY_NAME"
                    out += [context + [obj.__class__.__name__ + '::' + repr(sub)]]
                else:
                    # Step into this key's value, our context is expanded with "OBJ_CLASS[KEY_NAME]"
                    out += _scan_iterable(obj[sub], context=context[:]
                                          + [obj.__class__.__name__ + '[' + str(sub) + ']'])
            else:
                # Step into this value, our context is expanded with "OBJ_CLASS"
                # In JSON the index of the tuple or list entry shouldn't matter much, so we also keep these anonymous
                out += _scan_iterable(sub, context=context[:] + [obj.__class__.__name__])
    else:
        # We can't step into this object, so check if it is dumpable
        # If it is not, output "OBJ_CLASS::VALUE"
        undumpable = _is_undumpable(obj)
        if undumpable:
            out += [context + [obj.__class__.__name__ + '::' + undumpable]]
    return out


def dump(obj, fp, ensure_ascii=True):
    """
    Attempt to json.dump() an object to a 'file'. This function provides additional info if the object can't
    be serialized.

    :param obj: the object to serialize.
    :param fp: the file-like object to write to.
    :param ensure_ascii: allow binary strings to be sent
    """
    try:
        json.dump(obj, fp, ensure_ascii=ensure_ascii)
    except UnicodeDecodeError as e:
        undumpables = _scan_iterable(obj)
        traces = '\n\t'.join(['->'.join(u) for u in undumpables])
        error = UnicodeDecodeError(e.encoding, str(obj), e.start, e.end, "could not dump:\n\t%s" % traces)
        error.message = str(error)
        raise error


def dumps(obj, ensure_ascii=True):
    """
    Attempt to json.dumps() an object. This function provides additional info if the object can't be serialized.

    :param obj: the object to serialize.
    :param ensure_ascii: allow binary strings to be sent
    :return: the JSON str representation of the object.
    """
    try:
        return json.dumps(obj, ensure_ascii=ensure_ascii)
    except UnicodeDecodeError as e:
        undumpables = _scan_iterable(obj)
        traces = '\n\t'.join(['->'.join(u) for u in undumpables])
        error = UnicodeDecodeError(e.encoding, str(obj), e.start, e.end, "could not dump:\n\t%s" % traces)
        error.message = str(error)
        raise error


def twisted_dumps(obj, ensure_ascii=True):
    """
    Attempt to json.dumps() an object and encode it to convert it to bytes.
    This method is helpful when returning JSON data in twisted REST calls.

    :param obj: the object to serialize.
    :param ensure_ascii: allow binary strings to be sent
    :return: the JSON bytes representation of the object.
    """
    return dumps(obj, ensure_ascii).encode('utf-8')


def loads(s, *args, **kwargs):
    """
    Attempt to json.loads() a string. This function wraps json.loads, to provide dumps and loads from the same file.

    :param s: the JSON formatted string to load objects from.
    :return: the Python object(s) extracted from the JSON input.
    """
    return json.loads(s, *args, **kwargs)


def twisted_loads(s, *args, **kwargs):
    """
    Attempt to json.loads() a bytes. This function wraps json.loads, to provide dumps and loads from the same file.

    :param s: the JSON formatted bytes to load objects from.
    :return: the Python object(s) extracted from the JSON input.
    """
    return json.loads(s.decode('utf-8'), *args, **kwargs)


def load(fp, *args, **kwargs):
    """
    Attempt to json.load() from a 'file'. This function wraps json.load, to provide dump and load from the same file.

    :param s: the JSON formatted file-like object to load objects from.
    :return: the Python object(s) extracted from the JSON input.
    """
    return json.load(fp, *args, **kwargs)
