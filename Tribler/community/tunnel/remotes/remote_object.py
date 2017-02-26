import json
import logging
from binascii import hexlify, unhexlify


def shared(is_id=False):
    """
    Annotation function to flag a function as a field/property
    of an object which needs to be serialized and unserialized
    for synchronization across processes.

    :param is_id: this is the unique id of the class (for syncing)
    :param is_id: bool or func
    """
    def make_prop(f, id_field):
        def get_val(cls):
            return getattr(cls, '_' + f.__name__, None)
        def set_val(cls, x):
            if hasattr(cls, '_dirty_serializables'):
                getattr(cls,
                        '_dirty_serializables').add(f.__name__)
            else:
                setattr(cls,
                        '_dirty_serializables',
                        set([f.__name__,]))
            setattr(cls, '_' + f.__name__, x)
        prop = property(get_val,
                        set_val,
                        None,
                        '__is_id__' + str(id_field))
        return prop
    if callable(is_id):
        return make_prop(is_id, False)
    return lambda f: make_prop(f, is_id)


class RemoteObject(object):

    """
    A generic object which can be serialized and deserialized
    """

    def __is_dirty__(self):
        """
        Have any of the shared fields been modified

        :return: True iff any of the @shared fields have been modified
        :rtype: bool
        """
        if hasattr(self, '_dirty_serializables'):
            return len(self._dirty_serializables) > 0
        return False

    @staticmethod
    def __extract_class_name__(s):
        """
        Extract the class name from a serialized form

        :param s: the serialized object
        :type s: str
        :return: the class name
        :rtype: str
        """
        modif = s[:s.find(':')] + ':""}'
        struct = json.loads(modif)
        return struct.keys()[0]

    @classmethod
    def __serialize__(cls, instance, only_update=True):
        """
        Serialize an instance of a class to string

        :param cls: the RemoteObject class type to serialize as
        :type cls: type
        :param instance: the RemoteObject instance to serialize
        :type instance: RemoteObject
        :param only_update: only update modified fields, or everything
        :type only_update: bool
        :return: the string serialization of the instance
        :rtype: str
        """
        out = {}
        updatables = instance._dirty_serializables \
            if only_update\
            and hasattr(instance, '_dirty_serializables')\
            else cls.__dict__
        for f in cls.__dict__:
            doc = getattr(cls, f).__doc__
            if doc and doc.startswith('__is_id__'):
                if doc == '__is_id__True' or f in updatables:
                    value = getattr(instance, f)
                    if isinstance(value, basestring):
                        out[f] = hexlify(value)
                    elif isinstance(value, (tuple, list)):
                        out[f] = map(lambda x: hexlify(x)
                                     if isinstance(x, basestring)
                                     else x, value)
                    else:
                        out[f] = value
        if hasattr(instance, '_dirty_serializables'):
            instance._dirty_serializables.clear()
        try:
            return json.dumps({cls.__name__: out})
        except UnicodeDecodeError:
            logging.error("Failed to serialize " + str(out))
            return ""

    @classmethod
    def __unserialize__(cls, s, known={}):
        """
        Deserialize a string to a RemoteObject or update one

        :param cls: the RemoteObject class type to deserialize
        :type cls: type
        :param s: the string serialization
        :type s: str
        :param known: the id->obj dict of known objects
        :type known: dict
        :return: the object id and the deserialized object
        :rtype: (str, RemoteObject)
        """
        struct = json.loads(s)

        assert isinstance(struct, dict)
        assert len(struct.keys()) == 1
        assert struct.keys()[0] == cls.__name__

        # Find the id field
        # And check the integrity
        fields = struct[cls.__name__]
        id_field = None
        for f in fields:
            doc = getattr(cls, f).__doc__
            if doc and doc.startswith('__is_id__'):
                annotation = getattr(cls, f).__doc__[len('__is_id__'):]
                if annotation == "True":
                    if id_field:
                        logging.error("Multiple id fields declared")
                    id_field = f
            else:
                logging.error("Tried setting " + str(f)
                              + "which is not shared!")

        assert id_field

        id_val = unhexlify(fields[id_field])\
            if isinstance(fields[id_field], basestring)\
            else fields[id_field]

        # Retrieve the object by unique id
        # Or create a new object
        in_known = id_val in known
        out = known[id_val] if in_known else cls.__new__(cls)
        if not in_known:
            setattr(out, id_field, id_val)

        # Copy the fields from the input
        for f in fields:
            if f != id_field:
                val = None
                if isinstance(fields[f], basestring):
                    val = unhexlify(fields[f])
                elif isinstance(fields[f], list):
                    val = map(lambda x: unhexlify(x)
                              if isinstance(x, basestring)
                              else x, fields[f])
                else:
                    val = fields[f]
                setattr(out, f, val)

        return (id_val, out)
