# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""This module implements a SwitchPower UPnP Server."""

import types
from Tribler.UPnP.upnpserver import UPnPService

##############################################
# SWITCH POWER SERVICE
##############################################

class SwitchPower(UPnPService):

    """This class implements a simple SwitchPower service.
    The supported actions essentially allow clients to switch power
    on and off on a virtual device."""

    def __init__(self, service_id):
        UPnPService.__init__(self, service_id, 'SwitchPower',
                             service_version=1)
        boolean = types.BooleanType

        # Define EventVariables
        self._status = self.define_evented_variable("Status",
                                                    boolean, False)

        # Define Actions
        self.define_action(self.get_status,
                           out_args=[("ResultStatus", boolean )],
                           name="GetStatus")
        self.define_action(self.get_target,
                           out_args=[("RetTargetValue", boolean)],
                           name="GetTarget")
        self.define_action(self.set_target,
                           in_args=[("NewTargetValue", boolean)],
                           name="SetTarget")

        # Service State
        self._target = False

    def get_status(self):
        """Get the power status of the switch."""
        self.log("GetStatus %s" % self._status.get())
        return self._status.get()

    def get_target(self):
        """Get the target power status for the switch."""
        self.log("GetTarget %s" % self._target)
        return self._target

    def set_target(self, new_value):
        """Set the target power status for the switch.
        This also sets the status similarly at some point (immediately)."""
        self.log("SetTarget %s" % new_value)
        self._target = new_value
        # Could delay this one
        self._status.set(new_value)
