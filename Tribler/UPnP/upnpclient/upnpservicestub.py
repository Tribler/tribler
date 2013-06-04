# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""UPnP Service Stub implements a local stub for a remote UPnPService. """

import time
import exceptions
import types
import urlparse
import uuid
import Tribler.UPnP.common.upnpmarshal as upnpmarshal
import Tribler.UPnP.common.upnpsoap as upnpsoap
import Tribler.UPnP.common.asynchHTTPclient as httpclient

_HTTP_200_RESPONSE = "HTTP/1.1 200 OK"


def _parse_sub_response_header(response_header):
    """Parse Subscription response header. Response header is
    assumed to be a string."""
    if response_header == None:
        return None
    lines = response_header.split("\r\n")
    if lines[0] != _HTTP_200_RESPONSE:
        return None
    header_map = {}
    for line in lines[1:]:
        if len(line.strip()) > 0:
            elem_name, elem_value = line.split(":", 1)
            header_map[elem_name.strip().lower()] = elem_value.strip()
    duration = _get_duration(header_map)
    sid = _get_sid(header_map)
    return sid, duration


def _get_duration(header_map):
    """
    Get the Subscription duration (int) from
    header_map (dictionary).
    """
    if 'timeout' in header_map:
        duration = header_map['timeout'].split('-')[-1]
        if duration == 'infinite':
            return 0
        else:
            return int(duration)
    else:
        return None


def _get_sid(header_map):
    """
    Get the Subscription ID (uuid.UUID) from
    header_map (dictionary).
    """
    if 'sid' in header_map:
        return uuid.UUID(header_map['sid'].split(':')[-1])
    else:
        return None


#
# ACTION REQUEST HTTP HEADER
#

_ACTION_REQUEST_HDR_FMT = """POST %s HTTP/1.1\r
HOST: %s:%d\r
Content-Length: %d\r
Content-Type: text/xml; charset="utf-8"\r
SOAPACTION: "%s#%s"\r\n\r\n"""


def _get_action_request_hdr(url, length, service_type, action_name):
    """Return action request http header as string."""
    return _ACTION_REQUEST_HDR_FMT % (url.path,
                                      url.hostname,
                                      url.port, length,
                                      service_type,
                                      action_name)

#
# SUBSCRIBE REQUEST HTTP HEADER
#

_SUBSCRIBE_REQUEST_HDR_FMT = """SUBSCRIBE %s HTTP/1.1\r
HOST: %s:%d\r
CALLBACK: <%s>\r
NT: upnp:event\r
TIMEOUT: Second-%d\r\n\r\n"""


def _get_subscription_request_hdr(url, callback_url, seconds):
    """Return subscription request http header as string."""
    return _SUBSCRIBE_REQUEST_HDR_FMT % (url.path, url.hostname,
                                         url.port, callback_url, seconds)


#
# RENEW REQUEST HTTP HEADER
#

_RENEW_REQUEST_HDR_FMT = """SUBSCRIBE %s HTTP/1.1\r
HOST: %s:%d\r
SID: uuid:%s\r
TIMEOUT: Second-%d\r\n\r\n"""


def _get_renew_request_hdr(url, sid, seconds):
    """Return subscription renewal request http header as string."""
    return _RENEW_REQUEST_HDR_FMT % (url.path, url.hostname,
                                     url.port, sid, seconds)


#
# UNSUBSCRIBE REQUEST HTTP HEADER
#

_UNSUBSCRIBE_REQUEST_HDR_FMT = """UNSUBSCRIBE %s HTTP/1.1\r
HOST: %s:%d\r
SID: uuid:%s\r\n\r\n"""


def _get_unsubscribe_request_hdr(url, sid):
    """Return unsubscribe request http header as string."""
    return _UNSUBSCRIBE_REQUEST_HDR_FMT % (url.path,
                                           url.hostname, url.port, sid)


#
# ACTION ERROR
#
class ActionError (exceptions.Exception):

    """Error associated with invoking actions on a remote UPnP
    Service. """
    pass


#
# ACTION WRAPPER
#

class ActionWrapper:

    """
    Convenience wrapper of action invokations.
    This allows the actions to appear as named methods
    of the ServiceStub.
    res = stub.action_name(parameters)
    """
    def __init__(self, stub, action_name):
        self._stub = stub
        self._action_name = action_name

    def __call__(self, *args):
        """Callable object refers to action method of stub."""
        res = self._stub.action(self._action_name, list(args))
        if res == None:
            raise ActionError("Some Error")
        elif len(res) == 0:
            return None
        elif len(res) == 1:
            return res[0]
        else:
            return tuple(res)

#
# SUBSCRIPTION
#


class Subscription:

    """
    A Service Stub may hold a single subscription for events
    from the remote service. This is the local representation
    of the state of that subscription."""
    def __init__(self):
        self._sid = None
        self._expiry = None

    def is_valid(self):
        """Is subscription currently valid?"""
        if self._sid != None and self._expiry != None:
            if self._expiry < time.time():
                return True
        return False

    def cancel(self):
        """Cancel subscription."""
        self._sid = None
        self._expiry = None

    def set(self, sid, duration):
        """Update subscription by setting new sid/duration."""
        self._sid = sid
        self._expiry = time.time() + duration

    def get_sid(self):
        """Get Subscription ID."""
        return self._sid

    def get_expiry(self):
        """Get expiry timestamp."""
        return self._expiry


#
# EVENT DEF
#

class EventDef:

    """Event Definition."""
    def __init__(self, service_stub, sv_def):
        self._sv_def = sv_def
        self._service_stub = service_stub

    FMT = "EventDef: %s -> %s\n\tPyType(%s), UPnPType(%s)"

    def __str__(self):
        """String representation."""
        return EventDef.FMT % (
            self._service_stub.get_short_service_id(),
            self._sv_def['name'], self._sv_def['pyType'],
            self._sv_def['upnpType'])


#
# SV DEF
#

class SvDef:

    """State Variable Definition."""
    def __init__(self, service_stub, sv_def):
        self._sv_def = sv_def
        self._service_stub = service_stub

    def get_name(self):
        """Get name of State Variable."""
        return self._sv_def['name']

    def get_upnp_type(self):
        """"Get UPnP type of State Variable (string)."""
        return self._sv_def['upnpType']

    def get_python_type(self):
        """Get python type<object> of State Variable."""
        return self._sv_def['pyType']

    def get_default_value(self):
        """Get default value of State Variable."""
        return self._sv_def['defaultValue']

    def is_evented(self):
        """Return true if State Variable is evented."""
        return self._sv_def['sendEvents']

    FMT = "SvDef: %s -> %s\n\tPyType(%s), "
    FMT += "UPnPType(%s), Default(%s), Evented(%s)\n"

    def __str__(self):
        """String representation."""
        return SvDef.FMT % (self._service_stub.get_short_service_id(),
                            self.get_name(), self.get_python_type(),
                            self.get_upnp_type(), str(self.get_default_value()),
                            str(self.is_evented()))


#
# ACTION DEF
#

class ActionDef:

    """Action Definition. Referenset to input arguments and output
    results."""

    def __init__(self, service_stub, action_def):
        self._action_def = action_def
        self._service_stub = service_stub

    def get_name(self):
        """Get name of Action Definition."""
        return self._action_def['name']

    def get_inargs(self):
        """Get list of input arguments of Action Definition. Tuples of
        (name, pyType and upnpType)."""
        return [(arg['name'], arg['rsv']['pyType'], arg['rsv']['upnpType'])
                for arg in self._action_def['inargs']]

    def get_outargs(self):
        """Get list of result arguments of Action Definition. Tuples of
        (name, pyType and upnpType)."""
        return [(arg['name'], arg['rsv']['pyType'], arg['rsv']['upnpType'])
               for arg in self._action_def['outargs']]

    FMT = "ActionDef: %s -> %s\n\tInArgs: %s\n\tOutArgs: %s\n"

    def __str__(self):
        """String representation of Action Definition."""
        return ActionDef.FMT % \
            (self._service_stub.get_short_service_id(),
             self.get_name(), self.get_inargs(), self.get_outargs())


#
# UPNP SERVICE STUB
#

class UPnPServiceStub:

    """UPnPServiceStub is a stub that allows easy interaction with
    remote UPnPService."""

    def __init__(self, upnp_client, device, service, service_spec):
        # Device is dictionary containing device description
        # originating from xml device description.
        # Service is dictionary containing specifig service specification
        # originating from xml device description.
        # Service Spec is dictionary containing service specification
        # from xml service description.
        self._upnp_client = upnp_client
        self._synch_httpc = upnp_client.synch_httpc
        self._device = device
        self._service = service
        self._sv_def_map = {}  # name: svdef
        self._action_def_map = {}  # actionName: actiondef
        self._subscription = Subscription()
        self._base_callback_url = self._upnp_client.get_base_event_url()
        self._notify_handlers = []

        for sv_spec in service_spec['stateVariables']:
            self._define_state_variable(sv_spec)

        for action_spec in service_spec['actions']:
            self._define_action(action_spec)

    #
    # PRIVATE UTILITY
    #
    def _define_state_variable(self, sv_spec):
        """Define a state variable for the stub. Called as a result of parsing
        the xml service description."""
        try:
            sv_def = {}
            sv_def['name'] = name = sv_spec['name']
            sv_def['upnpType'] = upnp_type = str(sv_spec['dataType'])
            sv_def['pyType'] = upnpmarshal.loads_python_type(upnp_type)
            dvalue = sv_spec['defaultValue']
            if dvalue != None:
                dvalue = upnpmarshal.loads_data_by_upnp_type(upnp_type, dvalue)
            sv_def['defaultValue'] = dvalue
            sv_def['sendEvents'] = upnpmarshal.loads(bool,
                                                     sv_spec['sendEvents'])
            self._sv_def_map[name] = sv_def
        except upnpmarshal.MarshalError as why:
            print why
            return

    def _define_action(self, action_spec):
        """Define an action for the stub. Called as a result of parsing
        the xml service description."""
        # Set references to sv_def
        for arg_spec in action_spec['inargs'] + action_spec['outargs']:
            stv = self._sv_def_map[arg_spec['rsv']]
            arg_spec['rsv'] = stv
        self._action_def_map[action_spec['name']] = action_spec

    def _create_action_request(self, action_name, inargs):
        """Build action request as string given name and input arguments."""
        # Check inargs
        if action_name not in self._action_def_map:
            return None, None
        action_def = self._action_def_map[action_name]
        if not len(inargs) == len(action_def['inargs']):
            return None, None

        # Convert inargs from python objects to (name, value) strings
        args = []  # (name, data)
        for i in range(len(inargs)):
            inargdef = action_def['inargs'][i]
            stv = inargdef['rsv']
            # Dump python value according to upnptype.
            data = upnpmarshal.dumps_by_upnp_type(stv['upnpType'], inargs[i])
            args.append((inargdef['name'], data))

        # Create HTTP SOAP Request
        service_type = self.get_service_type()
        xmldata = upnpsoap.create_action_request(
            service_type, action_name, args)
        if xmldata == None:
            return None, None
        url = urlparse.urlparse(self._service['controlURL'])
        header = _get_action_request_hdr(url, len(xmldata),
                                         service_type, action_name)
        return action_def, header + xmldata

    def _http_request(self, url, http_request):
        """Blocking HTTP Request. Return HTTP Response (header, body)."""
        status, reply = self._synch_httpc.request(url.hostname,
                                                  url.port, http_request)
        if status == httpclient.SynchHTTPClient.OK:
            header, body = reply
            if header[:len(_HTTP_200_RESPONSE)] == _HTTP_200_RESPONSE:
                return header, body
            else:
                return None, None
        elif status == httpclient.SynchHTTPClient.FAIL:
            return None, None

    def _parse_action_response(self, action_def, xml_data):
        """Parse xml action response response. Return out arguments."""

        # Parse Response XML
        dictionary = upnpsoap.parse_action_response(xml_data)

        # Check Response
        if dictionary['service_type'] != self.get_service_type():
            return None
        if dictionary['action_name'] != action_def['name']:
            return None
        if len(dictionary['arguments']) != len(action_def['outargs']):
            return None

        # Convert result arguments (name, data) to python objects.
        outargs = []
        for i in range(len(action_def['outargs'])):
            outargdef = action_def['outargs'][i]
            stv = outargdef['rsv']
            if outargdef['name'] != dictionary['arguments'][i][0]:
                return None
            data = dictionary['arguments'][i][1]
            obj = upnpmarshal.loads_data_by_upnp_type(
                stv['upnpType'], data)
            outargs.append(obj)
        return outargs

    def notify(self, sid, seq, var_list):
        """Event notification delivered by UPnPClient."""
        for var_name, data in var_list:
            if var_name in self._sv_def_map:
                stv = self._sv_def_map[var_name]
                obj = upnpmarshal.loads_data_by_upnp_type(
                    stv['upnpType'], data)
                for handler in self._notify_handlers:
                    handler(var_name, int(seq), obj)

    def _subscribe(self, opname, seconds=1800):
        """Common logic for Subscribe, Renew and Unsubscribe."""
        url = urlparse.urlparse(self._service['eventSubURL'])
        # Create Request
        if opname == "subscribe":
            request = _get_subscription_request_hdr(url,
                                                    self.get_callback_url(),
                                                    seconds)
        elif opname == "renew":
            request = _get_renew_request_hdr(url,
                                             self._subscription.get_sid(),
                                             seconds)
        elif opname == "unsubscribe":
            request = _get_unsubscribe_request_hdr(url,
                                                   self._subscription.get_sid())
        response_header = self._http_request(url, request)[0]
        # Parse Response
        res = _parse_sub_response_header(response_header)
        if res == None:
            return False
        if opname == "unsubscribe":
            self._subscription.cancel()
            return True
        elif opname in ["subscribe", "renew"]:
            sid, duration = res
            if sid != None and duration != None:
                self._subscription.set(sid, duration)
                return True
            else:
                return False
        return False

    #
    # PUBLIC API
    #
    def get_service_id(self):
        """Return full service id of remote UPnPService."""
        return self._service['serviceId']

    def get_short_service_id(self):
        """Return short service id of remote UPnPService."""
        return self._service['serviceId'].split(":", 3)[3]

    def get_service_type(self):
        """Return service type of remote UPnPService."""
        return self._service['serviceType']

    def get_device_uuid(self):
        """Return uuid of parent device of remote UPnPService."""
        return self._device['uuid']

    def get_action_names(self):
        """Return action names supported by remote UPnPService."""
        return self._action_def_map.keys()

    def get_callback_url(self):
        """Get the URL where UPnPClient expects event notifications
        to be delivered.(String)"""
        return self._base_callback_url + "%s/%s" % (self.get_device_uuid(),
                                                    self.get_service_id())

    def get_sv_names(self):
        """Get names of state variables. (List of Strings)"""
        return self._sv_def_map.keys()

    def get_event_names(self):
        """Get names of evented state variables."""
        names = []
        for sv_def in self._sv_def_map.values():
            if sv_def['sendEvents']:
                names.append(sv_def['name'])
        return names

    def get_event_def(self, event_name):
        """Get Event Definition given name."""
        if event_name in self.get_event_names():
            return EventDef(self, self._sv_def_map[event_name])

    def get_sv_def(self, sv_name):
        """Get state variable definition given name."""
        if sv_name in self._sv_def_map:
            return SvDef(self, self._sv_def_map[sv_name])

    def get_action_def(self, action_name):
        """Get action definition given name. """
        if action_name in self._action_def_map:
            return ActionDef(self, self._action_def_map[action_name])

    def get_action(self, action_name):
        """Get callable action object given name."""
        if action_name in self.get_action_names():
            return ActionWrapper(self, action_name)

    def action(self, action_name, inargs=None):
        """Invoked to carry out action against remote UPnPService. Blocking."""
        if inargs == None:
            inargs = []
        action_def, request = self._create_action_request(action_name, inargs)
        if request == None:
            return None
        url = urlparse.urlparse(self._service['controlURL'])
        body = self._http_request(url, request)[1]
        if body == None:
            return None
        outargs = self._parse_action_response(action_def, body)
        if outargs == None:
            return None
        self.log("Action %s %s %s" % (action_def['name'], inargs, outargs))
        return outargs

    def log(self, msg):
        """Utility log object."""
        msg = "%s %s" % (self.get_short_service_id(), msg)
        self._upnp_client.logger.log("SERVICE", msg)

    def subscribe(self, handler):
        """Subscribe to events from remote UPnPService. Blocking."""
        if handler in self._notify_handlers:
            return True
        else:
            self._notify_handlers.append(handler)
        # Check validity
        if self._subscription.is_valid():
            return True
        else:
            # Remote Subscribe
            res = self._subscribe("subscribe", seconds=1800)
            if res:
                self.log("Subscribe " + self.get_short_service_id())
            return res

    def renew(self):
        """Renew subscription to events from remote UPnPService. Blocking."""
        res = self._subscribe("renew", seconds=1800)
        if res:
            self.log("Renew " + self.get_short_service_id())
        return res

    def unsubscribe(self, handler):
        """Unsubscribe from remote UPnPService. Blocking. """
        if handler in self._notify_handlers:
            self._notify_handlers.remove(handler)
        if len(self._notify_handlers) == 0:
            # Remove Unsubscribe
            res = self._subscribe("unsubscribe")
            if res:
                self.log("UnSubscribe " + self.get_short_service_id())
            return res
        else:
            return True

    def __getattr__(self, action_name):
        """Return callable action object when stub object is qualified with
        action name.
        res = stub.action_name(input_params)
        """
        if action_name in self.get_action_names():
            return ActionWrapper(self, action_name)
        else:
            raise AttributeError(action_name)
