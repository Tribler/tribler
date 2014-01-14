# Written by Njaal Borch
# see LICENSE.txt for license information
import logging

logger = logging.getLogger(__name__)


def to_unicode(string):
    """
    Function to change a string (unicode or not) into a unicode string
    Will try utf-8 first, then latin-1.
    TODO: Is there a better way?  There HAS to be!!!
    """

    if string.__class__ != str:
        return string
    try:
        return unicode(string, "utf-8")
    except:
        pass
    logger.warn("Warning: Fallback to latin-1 for unicode conversion")
    return unicode(string, "latin-1")


class XmlPrinter:

    """
    An XML printer that will print XML *with namespaces*

    Why minidom.toxml() does not do so really makes absolutenly no sense

    """

    def __init__(self, doc):
        """
        doc should be a xml.dom.minidom document

        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.root = doc
        self.namespace_counter = 0

    def to_xml(self, encoding="UTF8"):
        """
        Like minidom toxml, just using namespaces too
        """
        return self._toxml(self.root, indent='', newl='').encode(encoding, "replace")

    def to_pretty_xml(self, indent=' ', newl='\n', encoding="UTF8"):
        """
        Like minidom toxml, just using namespaces too
        """
        return self._toxml(self.root, indent, newl).encode(encoding, "replace")

    def _make_header(self, encoding):

        return u'<?xml version="1.0" encoding="%s" ?>\n' % encoding

    def _new_namespace(self, namespace):
        # Make new namespace
        ns_short = "ns%d" % self.namespace_counter
        self.namespace_counter += 1
        return ns_short

    def _toxml(self, element, indent=' ', newl='\n', encoding='UTF8', namespaces=None):
        """
        Recursive, internal function - do not use directly
        """

        if not element:
            return ""

        if not namespaces:
            namespaces = {}
        buffer = u""
        define_ns_list = []

        if element == self.root:
            # Print the header
            buffer = self._make_header(encoding)

        if element.nodeType == element.TEXT_NODE:
            buffer += indent + to_unicode(element.nodeValue) + newl
            return buffer
        if element.nodeType == element.ELEMENT_NODE:
            ns = element.namespaceURI
            name = to_unicode(element.localName)
            if name.find(" ") > -1:
                raise Exception("Refusing spaces in tag names")

            if ns in namespaces:
                ns_short = namespaces[ns]
                define_ns = False
            else:
                if ns not in ["", None]:
                    ns_short = self._new_namespace(ns)
                    define_ns_list.append((ns, ns_short))
                else:
                    ns_short = None

                define_ns = True
                namespaces[ns] = ns_short

            # Should we define more namespaces?  Will peak into the
            # children and see if there are any
            for child in element.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue

                if child.namespaceURI not in namespaces and \
                    child.namespaceURI not in [None, ""]:
                    # Should define this one too!
                    new_ns = self._new_namespace(child.namespaceURI)
                    define_ns_list.append((child.namespaceURI, new_ns))
                    namespaces[child.namespaceURI] = new_ns
            buffer += indent

            # If we have no children, we will write <tag/>
            if not element.hasChildNodes():
                if ns != None:
                    if define_ns:
                        if ns_short:
                            buffer += '<%s:%s xmlns:%s="%s"/>%s' %\
                                      (ns_short, name, ns_short, ns, newl)
                        else:
                            buffer += '<%s xmlns="%s"/>%s' % (name, ns, newl)
                    else:
                        if ns_short:
                            buffer += '<%s:%s/>%s' % (ns_short, name, newl)
                        else:
                            buffer += '<%s/>%s' % (name, newl)

                else:
                    buffer += '<%s/>%s' % (name, newl)

                # Clean up - namespaces is passed as a reference, and is
                # as such not cleaned up.  Let it be so to save some speed
                for (n, short) in define_ns_list:
                    del namespaces[n]
                return buffer

            # Have children
            ns_string = ""
            if len(define_ns_list) > 0:
                for (url, short) in define_ns_list:
                    ns_string += ' xmlns:%s="%s"' % (short, url)

            if ns != None:
                if define_ns:
                    if ns_short:
                        # Define all namespaces of next level children too
                        buffer += '<%s:%s xmlns:%s="%s"%s>%s' %\
                                  (ns_short, name, ns_short, ns, ns_string, newl)
                    else:
                        buffer += '<%s xmlns="%s"%s>%s' % (name, ns, ns_string, newl)
                else:
                    if ns_short:
                        buffer += '<%s:%s%s>%s' % (ns_short, name, ns_string, newl)
                    else:
                        buffer += '<%s%s>%s' % (name, ns_string, newl)
            elif ns_string:
                buffer += '<%s %s>%s' % (name, ns_string, newl)
            else:
                buffer += '<%s>%s' % (name, newl)

            # Recursively process
            for child in element.childNodes:
                new_indent = indent
                if new_indent:
                    new_indent += "  "
                buffer += self._toxml(child, new_indent, newl, encoding, namespaces)
            if ns_short:
                buffer += "%s</%s:%s>%s" % (indent, ns_short, name, newl)
            else:
                buffer += "%s</%s>%s" % (indent, name, newl)

            for (n, short) in define_ns_list:
                del namespaces[n]
            try:
                return buffer
            except Exception as e:
                self._logger.error("-----------------")
                self._logger.error("Exception: %s" % repr(e))
                self._logger.error("Buffer: %s" % repr(buffer))
                self._logger.error("-----------------")
                raise e

        raise Exception("Could not serialize DOM")
