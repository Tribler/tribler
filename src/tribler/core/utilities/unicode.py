"""
Conversions to unicode.

Author(s): Arno Bakker
"""
import binascii

import chardet


def ensure_unicode(s, encoding, errors='strict'):
    """Similar to six.ensure_text() except that the encoding parameter is *not* optional
    """
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    elif isinstance(s, str):
        return s
    else:
        raise TypeError(f"not expecting type '{type(s)}'")


def ensure_unicode_detect_encoding(s):
    """Similar to ensure_unicode() but use chardet to detect the encoding
    """
    if isinstance(s, bytes):
        try:
            return s.decode('utf-8')  # Try converting bytes --> Unicode utf-8
        except UnicodeDecodeError:
            charenc = chardet.detect(s)['encoding']
            return s.decode(charenc) if charenc else s  # Hope for the best
    elif isinstance(s, str):
        return s
    else:
        raise TypeError(f"not expecting type '{type(s)}'")


def recursive_unicode(obj, ignore_errors=False):
    """
    Converts any bytes within a data structure to unicode strings. Bytes are assumed to be UTF-8 encoded text.
    :param obj: object comprised of lists/dicts/strings/bytes
    :return: obj: object comprised of lists/dicts/strings
    """
    if isinstance(obj, dict):
        return {recursive_unicode(k, ignore_errors): recursive_unicode(v, ignore_errors) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_unicode(i, ignore_errors) for i in obj]
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf8')
        except UnicodeDecodeError:
            if ignore_errors:
                return "".join(chr(c) for c in obj)
            raise
    return obj


def recursive_ungarble_metainfo(obj):
    if isinstance(obj, dict):
        return {k: recursive_ungarble_metainfo(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_ungarble_metainfo(i) for i in obj]
    elif isinstance(obj, str):
        return bytes(ord(c) for c in obj)
    return obj


def recursive_bytes(obj):
    """
    Converts any unicode strings within a Python data structure to bytes. Strings will be encoded using UTF-8.
    :param obj: object comprised of lists/dicts/strings/bytes
    :return: obj: object comprised of lists/dicts/bytes
    """
    if isinstance(obj, dict):
        return {recursive_bytes(k): recursive_bytes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_bytes(i) for i in obj]
    elif isinstance(obj, str):
        return obj.encode('utf8')
    return obj


def hexlify(binary):
    return binascii.hexlify(binary).decode('utf-8')
