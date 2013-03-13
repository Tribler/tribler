# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""
This module implements a UPnP Service.

This involves a base class intended for development of new services.
The baseclass hides complexity related to producing UPnP Service
description in both XML and HTML format. It also hides complexity
related to the placement of a service within a device hierarchy.
"""
import types
import uuid
import exceptions
import Tribler.UPnP.common.upnpmarshal as upnpmarshal

class ActionError (exceptions.Exception):
    """Error associated with invoking actions on a UPnP Server. """
    pass

##############################################
# XML FMT
##############################################

_SERVICE_DESCRIPTION_FMT = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<actionList>
%s</actionList>
<serviceStateTable>
%s</serviceStateTable>
</scpd>"""

_ACTION_FMT = """<action>
<name>%s</name>
<argumentList>
%s
</argumentList>
</action>
"""

_ARGUMENT_FMT = """<argument>
<name>%s</name>
<relatedStateVariable>%s</relatedStateVariable>
<direction>%s</direction>
</argument>"""

_EVENTED_VARIABLE_FMT = """<stateVariable sendEvents="yes">
<name>%s</name>
<dataType>%s</dataType>
<defaultValue>%s</defaultValue>
</stateVariable>
"""

_ARG_VARIABLE_FMT = """<stateVariable sendEvents="no">
<name>%s</name>
<dataType>%s</dataType>
</stateVariable>
"""

def _service_description_toxml(service):
    """This function produces the UPnP XML service description."""

    svs_str = ""
    # Evented Variables
    for evar in service.get_evented_variables():
        data_type = upnpmarshal.dumps_data_type(evar.the_type)
        default_value = upnpmarshal.dumps(evar.default_value)
        args = (evar.the_name, data_type, default_value)
        svs_str += _EVENTED_VARIABLE_FMT % args

    actions_str = ""
    arg_counter = 0

    # One state variable per type (event variables of arguments)
    unique_variables = {} # type : variable name
    for evar in service.get_evented_variables():
        if not unique_variables.has_key(evar.the_type):
            unique_variables[evar.the_type] = evar.the_name

    # Arguments
    for action in service.get_actions():
        args_str = ""
        for arg in action.in_arg_list + action.out_arg_list:

            # Check if argument can be related to event variable
            if unique_variables.has_key(arg.the_type):
                related_variable_name = unique_variables[arg.the_type]
            else:
                arg_counter += 1
                related_variable_name = "A_ARG_TYPE_%d" % arg_counter
                unique_variables[arg.the_type] = related_variable_name
                # New State Variable
                data_type = upnpmarshal.dumps_data_type(arg.the_type)
                svs_str += _ARG_VARIABLE_FMT % (related_variable_name,
                                                data_type)

            # New Argument
            direction = 'in' if isinstance(arg, _InArg) else 'out'
            args_str += _ARGUMENT_FMT % (arg.the_name,
                                         related_variable_name, direction)
        # Action
        actions_str += _ACTION_FMT % (action.name, args_str)

    return _SERVICE_DESCRIPTION_FMT % (actions_str, svs_str)



##############################################
# UPNP SERVICE
##############################################

class UPnPService:

    """
    This implements a base class for all UPnP Services.

    New services should extend this class.
    The base class hides complexity related to production
    of XML service descriptions as well as HTTP descriptions.
    The base class also hides complexity related to placement
    in the UPnP device hierarchy.
    """

    def __init__(self, service_id, service_type, service_version=1):
        self.service_manager = None

        self._actions = {} # actionName : Action
        self._events = {} # eventName : Event
        self._subs = {} # callbackURL : Subscriptions

        # Initialise
        self.service_type = service_type
        self.service_version = service_version
        self.service_id =  service_id

        self.base_url = ""
        self.description_path = ""
        self.control_path = ""
        self.event_path = ""
        self._logger = None

    def set_service_manager(self, service_manager):
        """Initialise UPnP service with reference to service manager."""
        self.service_manager = service_manager
        self.base_url = self.service_manager.get_base_url()
        self.description_path = "services/%s/description.xml" % self.service_id
        self.control_path = "services/%s/control" % self.service_id
        self.event_path = "services/%s/events" % self.service_id
        # Logging
        self._logger = self.service_manager.get_logger()

    def is_valid(self):
        """Check if service is valid."""
        return (self.service_type != None and self.service_id != None
                and self.base_url != None and self.service_manager != None)

    def get_short_service_id(self):
        """Return short service id."""
        return self.service_id

    def get_service_id(self):
        """Return full service id."""
        return "urn:upnp-org:serviceId:%s" % self.service_id

    def get_service_type(self):
        """Return service type."""
        fmt = "urn:schemas-upnp-org:service:%s:%s"
        return  fmt % (self.service_type, self.service_version)

    def get_xml_description(self):
        """Returns xml description of service."""
        return _service_description_toxml(self)

    def close(self):
        """Close UPnP service safely."""
        for sub in self._subs.values():
            sub.close()

    ##############################################
    # LOG API
    ##############################################

    def log(self, msg):
        """Logger."""
        if self._logger:
            self._logger.log("SERVICE", "%s %s" % (self.service_id, msg))

    ##############################################
    # SUBSCRIBE / NOTIFY API
    ##############################################

    def notify(self, evented_variables):
        """Notify all subscribers of updated event variables."""
        self._remove_expired_subscriptions()
        # Dispatch Event Messages to all subscribers
        # of the given serviceid.
        # Make sure all stateVariables are evented variables.
        for sub in self._subs.values():
            sub.notify(evented_variables)

    def subscribe(self, callback_urls, requested_duration):
        """Process new subscription request."""
        # requested duration == 0 => infinite
        self._remove_expired_subscriptions()
        # For the moment, just accept a single callbackUrl
        # Subscriber defined by callbackUrl
        callback_url = callback_urls[0]
        if self._subs.has_key(callback_url):
            # Subscriber already exists
            return (None, None)
        else:
            # Add new Subscriber
            sub = _Subscription(self, callback_url, requested_duration)
            self._subs[callback_url] = sub
            # Dispatch Initial Event Message
            sub.initial_notify()
            return (sub.sid, sub.duration)

    def renew(self, sid_str, requested_duration):
        """Request to renew an existing subscription."""
        # requested duration == 0 => infinite
        for sub in self._subs.values():
            if str(sub.sid) == sid_str:
                return sub.renew(requested_duration)
        else: return None

    def unsubscribe(self, sid_str):
        """Request to unsubscribe an existing subscription."""
        sub = None
        for sub in self._subs.values():
            if str(sub.sid) == sid_str:
                break
        if sub:
            sub.cancel()
            del self._subs[sub.callback_url]
            return True
        else:
            return False

    def _remove_expired_subscriptions(self):
        """Scans subscriptions and removes invalidated."""
        for url, sub in self._subs.items()[:]:
            if sub.is_expired:
                del self._subs[url]


    ##############################################
    # ACTION API
    ##############################################

    def define_action(self, method, in_args=None, out_args=None,
                      name=None):
        """Define an action that the service implements.
        Used by subclass."""
        if not in_args:
            in_args = []
        if not out_args:
            out_args = []
        if not name:
            action_name = method.__name__
        else:
            action_name = name
        # In/Out Args must be tuples of (name, type<?>)
        in_args = [_InArg(t[0], t[1]) for t in in_args]
        out_args = [_OutArg(t[0], t[1]) for t in out_args]
        action = _Action(action_name, method, in_args, out_args)
        self._actions[action_name] = action

    def invoke_action(self, action_name, in_args):
        """Invoke and action that the service implements.
        Used by httpserver as part of UPnP control interface."""
        # in_args is assumed to be tuple of (name, data) all unicode string.
        try:
            if not self._actions.has_key(action_name):
                raise ActionError, "Action Not Supported"
            else:
                action = self._actions[action_name]
                return action.execute(in_args)
        except ActionError, why:
            print why

    def get_actions(self):
        """Returns all actions that the service implements."""
        return self._actions.values()


    ##############################################
    # EVENTED VARIABLE API
    ##############################################

    def define_evented_variable(self, event_name, the_type, default_value):
        """Define an evented variable for the service. Used by subclass."""
        evar = _EventedVariable(self, event_name, the_type, default_value)
        self._events[event_name] = evar
        return evar

    def get_evented_variable(self, event_name):
        """Return evented variable given name."""
        return self._events.get(event_name, None)

    def get_evented_variables(self):
        """Return all evented variables defined by the service."""
        return self._events.values()

    def set_evented_variables(self, list_):
        """
        Update a list of state variables at once.
        Input will be a list of tuples [(eventedVariable, newValue)]
        The method avoids sending one notification to every subscriber,
        for each state variable. Instead, a single subscriber receives
        one eventMessage containing all the updated state Variables
        in this list.
        """
        # Update Values
        changed_variables = []
        for evar, new_value in list_:
            changed = evar.set(new_value, notify_ok=False)
            if changed:
                changed_variables.append(evar)
        # notify all in one batch
        self.notify(changed_variables)


##############################################
# EVENTED VARIABLE
##############################################

class _EventedVariable:

    """This class defines an evented variable. The class hides
    complexity related to event notification."""

    def __init__(self, service, the_name, the_type, default_value):
        self._service = service
        self.the_name = the_name
        if type(the_type) == types.TypeType:
            self.the_type = the_type
        else:
            msg = "Argument 'the_type' is not actually a python type."
            raise TypeError,  msg
        self._value = default_value
        self.default_value = default_value

    def set(self, new_value, notify_ok=True):
        """Set a new value for the evented variable. If the value
        is different from the old value, notifications will be generated."""
        if type(new_value) != self.the_type:
            msg = "Argument 'the_type' is not actually a python type."
            raise TypeError, msg
        if new_value != self._value:
            # Update Value
            self._value = new_value
            # Notify
            if notify_ok:
                self._service.notify([self])
            return True
        else : return False

    def get(self):
        """Get the value of an evented variable."""
        return self._value


##############################################
# ARGUMENT
##############################################

class _Argument :

    """The class defines an argument by holding a type and
    and argument name."""
    def __init__(self, the_name, the_type):
        self.the_name = the_name
        self.the_type = the_type

class _InArg(_Argument):
    """The class defines an input argument by holding a type and
    and argument name."""
    pass

class _OutArg(_Argument):
    """The class defines an output argument (result value) by
    holding a type and and argument name."""
    pass

##############################################
# ACTION
##############################################

class _Action:

    """This class represents an action implemented by the
    service."""

    def __init__(self, name, method, in_arg_list, out_arg_list):
        self.name = name
        self.method = method
        self.in_arg_list = in_arg_list
        self.out_arg_list = out_arg_list

    def execute(self, in_args):
        """Execute the action."""
        # in_args is assumed to be tuple of (name, data) all unicode string.
        # the tuple is supposed to be ordered according to in_arg_list
        if len(in_args) != len(self.in_arg_list):
            raise ActionError, "Wrong number of input arguments"
        typed_args = []
        for i in range(len(in_args)):
            name, data = in_args[i]
            in_arg = self.in_arg_list[i]
            if name != in_arg.the_name:
                raise ActionError, "Wrong name/order for input argument"
            try:
                value = upnpmarshal.loads(in_arg.the_type, data)
            except upnpmarshal.MarshalError, why:
                raise ActionError, why
            typed_args.append(value)

        # Execute
        try:
            result = self.method(*typed_args)
        except TypeError, why:
            raise ActionError, "Method Execution Failed (%s)" % why

        # Result is eiter a single value (incl. None) or a tuple of values.
        # Make it into a list in both cases.
        if result == None:
            result = []
        elif result == types.TupleType:
            result = list(result)
        else:
            result = [result]

        # Check that result holds the correct number of values
        if len(result) != len(self.out_arg_list):
            raise ActionError, "Wrong number of Results"
        # Check that each value has the correct type
        # Also convert python type objects to string representations.
        # Construct out_args list of tuples [(name, data), ...]
        out_args = []
        for i in range(len(result)):
            out_arg = self.out_arg_list[i]
            value = result[i]
            if not isinstance(value, out_arg.the_type):
                raise ActionError, "Result is wrong type."
            else:
                try:
                    data = upnpmarshal.dumps(value)
                except upnpmarshal.MarshalError, why:
                    raise ActionError, why
                out_args.append((out_arg.the_name, data))
        return out_args


##############################################
# SUBSCRIPTION
##############################################

class NotifyError (exceptions.Exception):
    """Error associated with event notification."""
    pass

class _Subscription:

    """This class represents a subscription made to the service,
    for notification whenever one of its evented variables is updated."""

    def __init__(self, service, callback_url, requested_duration):
        # requested_duration == 0 implies INFINITE
        # requested_duration > 0 implies FINITE
        # requested_duration < 0 not legal
        self.service = service
        self.sid = uuid.uuid1()
        self.event_key = 0
        self.callback_url = callback_url
        self.duration = 1800 # ignore requested_duration
        self.is_expired = False

    def notify(self, evented_variables):
        """Notify this subscriber that given evented variables
        have been updated."""
        if self.is_expired :
            return False # should not be neccesary
        else:
            self.event_key += 1
            # Construct list of tuples [(name, value), ...]
            variables = []
            for evar in evented_variables:
                try:
                    data = upnpmarshal.dumps(evar.get())
                except upnpmarshal.MarshalError, why:
                    raise NotifyError, why
                variables.append((evar.the_name, data))

            # Dispatch Notification
            edp = self.service.service_manager.get_event_dispatcher()
            edp.dispatch(self.sid, self.event_key, self.callback_url, variables)
            return True

    def initial_notify(self):
        """Notify this subscriber of all evented state
        variables and their values"""
        if self.is_expired:
            return False
        # Event Key must be 0
        if self.event_key != 0:
            return False
        # All Evented Variables
        evented_variables = self.service.get_evented_variables()
        variables = []
        for evar in evented_variables:
            try:
                data = upnpmarshal.dumps(evar.get())
            except upnpmarshal.MarshalError, why:
                raise NotifyError, why
            variables.append((evar.the_name, data))

        # Dispatch Notification
        edp = self.service.service_manager.get_event_dispatcher()
        edp.dispatch(self.sid, 0, self.callback_url, variables)
        return True

    def renew(self, requested_duration):
        """Renew subscription for this subscriber."""
        self.duration = requested_duration
        self.is_expired = False
        return self.duration

    def cancel(self):
        """Cancel subscription for this subscriber."""
        self.is_expired = True
        return True

    def close(self):
        """Close this subscription safely."""
        pass

##############################################
# MAIN
##############################################

if __name__ == '__main__':

    class MockEventDispatcher:
        """Mock Event Dispatcher."""
        def __init__(self):
            pass
        def dispatch(self, sid, event_key, callback_url, variables):
            """Mock method."""
            print "Notify", sid, event_key, callback_url, variables

    class MockServiceManager:
        """Mock Service Manager."""
        def __init__(self):
            self._ed = MockEventDispatcher()
        def get_event_dispatcher(self):
            """Mock method."""
            return self._ed
        def get_base_url(self):
            """Mock method."""
            return "http://myhost:44444"
        def get_logger(self):
            """Mock method."""
            return None

    SM = MockServiceManager()
    from Tribler.UPnP.services import SwitchPower
    SERVICE = SwitchPower('SwitchPower')
    SERVICE.set_service_manager(SM)
    print SERVICE.get_xml_description()
