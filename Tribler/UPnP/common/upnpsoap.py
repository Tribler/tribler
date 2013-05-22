# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements parsing and creation of soap messages
specified by the UPnP specification, action requests, action responses,
error responses and event messages.
"""
import xml.dom.minidom as minidom

ERROR_CODES = {
    401: "Invalid Action",
    402: "Invalid Args",
    501: "Action Failed",
    600: "Argument Value Invalid",
    601: "Argument Value Out of Range",
    602: "Optional Action Not Implemented",
    603: "Out of Memory",
    604: "Human Intervention Required",
    605: "String Argument Too Long",
    606: "Action Not Authorized",
    607: "Signature Failure",
    608: "Signature Missing",
    609: "Not Encrypted",
    610: "Invalid Sequence",
    611: "Invalid Control URL",
    612: "No Such Session",
}


def _get_element_data(element):
    """Get all data contained in element."""
    data = ""
    if element != None:
        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                data += str(node.data)
            elif node.nodeType == node.ELEMENT_NODE:
                data += str(node.toxml())
            elif node.nodeType == node.CDATA_SECTION_NODE:
                data += str(node.data)
    return data

#
# PARSE ACTION REQUEST
#


class _ActionRequest:

    """This implements parsing of action requests made by
    UPnP control points. The soap message corresponds to
    the body of the HTTP POST request."""

    def __init__(self):
        self._doc = None
        self._action_name = ""
        self._ns = ""
        self._args = []

    def parse(self, xmldata):
        """This parses the xmldata and makes the included information
        easily accessible."""
        try:
            doc = minidom.parseString(xmldata.replace('\n', ''))
            envelope = doc.documentElement
            body = envelope.firstChild
            action_element = body.firstChild
            args = []
            for arg_element in action_element.childNodes:
                data = _get_element_data(arg_element)
                args.append((str(arg_element.tagName), data))
        except (TypeError, AttributeError):
            return False

        self._doc = doc
        self._action_name = action_element.localName
        self._ns = action_element.namespaceURI
        self._args = args
        return True

    def get_action_name(self):
        """Retrieve the name of the requested UPnP action."""
        if self._doc:
            return self._action_name

    def get_namespace(self):
        """Retrieve the namespace of the requested UPnP action,
        i.e. the service type it refers to."""
        if self._doc:
            return self._ns

    def get_arguments(self):
        """Retrieve the in-arguments associated with
        the UPnP action request."""
        if self._doc:
            return self._args

    def reset(self):
        """Reset so that a new soap message may be parsed by the
        same instance."""
        if self._doc:
            self._doc.unlink()
            self._doc = None
        self._action_name = ""
        self._ns = ""
        self._args = []


_INSTANCE = _ActionRequest()


def parse_action_request(data):
    """This function parses the soap xml request and
    returns three values. The function hides the details of
    implementation.

    action -- name of action
    ns -- namespace (i.e. service type)
    args -- action in-arguments.
    """
    success = _INSTANCE.parse(data)
    if not success:
        return None
    else:
        action_name = _INSTANCE.get_action_name()
        name_space = _INSTANCE.get_namespace()
        args = _INSTANCE.get_arguments()
        _INSTANCE.reset()
        return action_name, name_space, args


#
# CREATE ACTION REQUEST
#

ACTION_REQUEST_FMT = """<?xml version="1.0"?>
<s:Envelope
s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding"
xmlns:s="http://schemas.xmlsoap.org/soap/envelope">
<s:Body>
<u:%s
xmlns:u="%s">
%s
</u:%s>
</s:Body>
</s:Envelope>
"""
ACTION_REQUEST_FMT = ACTION_REQUEST_FMT.replace('\n', '')

ARG_FMT = "<%s>%s</%s>"


def create_action_request(service_type, action_name, args):
    """Create action request. Returns string."""
    data_str = ""
    for arg_name, arg_value in args:
        data_str += ARG_FMT % (arg_name, arg_value, arg_name)
    return ACTION_REQUEST_FMT % (action_name, service_type,
                                 data_str, action_name)


#
# CREATE ACTION RESPONSE
#

ACTION_RESPONSE_FMT = u"""<?xml version="1.0"?>
<s:Envelope
s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding"
xmlns:s="http://schemas.xmlsoap.org/soap/envelope">
<s:Body>
<u:%sResponse
xmlns:u="%s">
%s
</u:%sResponse>
</s:Body>
</s:Envelope>"""

ACTION_RESPONSE_FMT = ACTION_RESPONSE_FMT.replace('\n', '')

RESULT_FMT = u"<%s>%s</%s>"


def create_action_response(name_space, action_name, result_list):
    """This function creates a soap xml action response,
    given three parameters.

    name_space -- namespace (i.e. upnp service type)
    action_name -- name of upnp action
    result_list -- list of result values, i.e. (argName, argValue) - tuples
    """
    name_space = unicode(name_space)
    action_name = unicode(action_name)
    data_str = ""
    for (result_name, result_value) in result_list:
        result_name = unicode(result_name)
        result_value = unicode(result_value)
        data_str += RESULT_FMT % (result_name, result_value, result_name)
    return ACTION_RESPONSE_FMT % (action_name, name_space, data_str, action_name)


#
# PARSE ACTION RESPONSE
#
def parse_action_response(xmldata):
    """This parses the xmldata and makes the included information
    easily accessible."""
    try:
        doc = minidom.parseString(xmldata.replace('\n', ''))
        if doc == None:
            return None
        envelope_elem = doc.documentElement
        body_elem = envelope_elem.firstChild
        action_elem = body_elem.firstChild
        args = []
        for arg_elem in action_elem.childNodes:
            data = _get_element_data(arg_elem)
            args.append((str(arg_elem.tagName), data))
    except (TypeError, AttributeError):
        return None

    result = {}
    # actionNameResponse
    result['action_name'] = str(action_elem.localName[:-8])
    result['service_type'] = str(action_elem.namespaceURI)
    result['arguments'] = args
    return result


#
# ERROR RESPONSE
#


ERROR_RESPONSE_FMT = u"""<?xml version="1.0" ?>
<s:Envelope
s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding"
xmlns:s="http://schemas.xmlsoap.org/soap/envelope">
<s:Body>
<s:Fault>
<faultcode>s:Client</faultcode>
<faultstring>UPnPError</faultstring>
<detail>
<UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
<errorCode>%s</errorCode>
<errorDescription>%s</errorDescription>
</UPnPError>
</detail>
</s:Fault>
</s:Body>
</s:Envelope>
"""
ERROR_RESPONSE_FMT = ERROR_RESPONSE_FMT.replace('\n', '')


def create_error_response(error_code, error_description):
    """This function creates a soap xml UPnP error response."""
    error_code = unicode(error_code)
    error_description = unicode(error_description)
    return ERROR_RESPONSE_FMT % (error_code, error_description)


#
# CREATE EVENT MESSAGE
#

_EVENT_MSG_XML_FMT = u"""<?xml version="1.0"?>
<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
%s</e:propertyset>"""
_EVENT_MSG_PROP_FMT = u"<e:property>\n<%s>%s</%s>\n</e:property>\n"


def create_event_message(variables):
    """This function creates a soap xml UPnP event message.

    variables -- list of recently update state variables (name, data) tuples.
    """
    data_str = ""
    for name, data in variables:
        name = unicode(name)
        data = unicode(data)
        data_str += _EVENT_MSG_PROP_FMT % (name, data, name)
    return _EVENT_MSG_XML_FMT % data_str


#
# PARSE EVENT MESSAGE
#

def parse_event_message(xmldata):
    """This parses the xmldata and makes the included information
    easily accessible."""
    doc = minidom.parseString(xmldata.replace('\n', ''))
    if doc == None:
        return None
    property_set_elem = doc.documentElement
    tuples = []
    for property_elem in property_set_elem.childNodes:
        var_elem = property_elem.firstChild
        data = _get_element_data(var_elem)
        tuples.append((str(var_elem.tagName), data))
    return tuples


#
# MAIN
#

if __name__ == '__main__':

    REQUEST_XML = """<?xml version="1.0"?>
<s:Envelope
s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
<s:Body>
<ns0:SetTarget xmlns:ns0="urn:schemas-upnp-org:service:SwitchPower:1">
<newTargetValue>True</newTargetValue>
</ns0:SetTarget>
</s:Body>
</s:Envelope>"""

    REQUEST_XML = REQUEST_XML.replace('\n', '')
    print parse_action_request(REQUEST_XML)
    print parse_action_request(REQUEST_XML)

    SERVICE_TYPE = "urn:schemas-upnp-org:service:ServiceType:1"
    ACTION_NAME = "GetTarget"
    RESULT_LIST = [('result1', 'True'), ('result2', '4')]
    RESPONSE_XML = create_action_response(SERVICE_TYPE,
                                          ACTION_NAME, RESULT_LIST)
    print RESPONSE_XML
    print create_error_response("501", "Action not implemented")

    VARIABLES = [('var1', 'jalla'), ('var2', 'palla')]
    EVENT_MSG = create_event_message(VARIABLES)
    print EVENT_MSG
    print parse_event_message(EVENT_MSG)

    print create_action_request(SERVICE_TYPE,
                                ACTION_NAME, VARIABLES)

    print parse_action_response(RESPONSE_XML)
