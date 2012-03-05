from random import random
from community import EffortCommunity

from Tribler.Core.dispersy.dprint import dprint
from Tribler.Core.dispersy.tool.scenarioscript import ScenarioScript as ScenarioScriptBase, ScenarioExpon

class ScenarioScript(ScenarioScriptBase, ScenarioExpon):
    @property
    def master_member_public_key(self):
        return "3081a7301006072a8648ce3d020106052b81040027038192000404668ed626c6d6bf4a280cf4824c8cd31fe4c7c46767afb127129abfccdf8be3c38d4b1cb8792f66ccb603bfed395e908786049cb64bacab198ef07d49358da490fbc41f43ade33e05c9991a1bb7ef122cda5359d908514b3c935fe17a3679b6626161ca8d8d934d372dec23cc30ff576bfcd9c292f188af4142594ccc5f6376e2986e1521dc874819f7bcb7ae3ce400".decode("HEX")

    @property
    def community_class(self):
        return EffortCommunity

    @property
    def community_args(self):
        return (self.__class,)

    def scenario_classes(self, *classes):
        options = [(t[0], float(t[1])) for t in (s.split(":") for s in classes)]
        value = random() * sum(weight for _, weight in options)
        for class_, weight in options:
            value -= weight
            if value <= 0.0:
                self.__class = class_
                break
        dprint("choosing class ", self.__class)

    def scenario_online_beta(self, *classes):
        options = [(t[0], float(t[1])) for t in (s.split(":") for s in classes)]
        for class_, online_beta in options:
            if class_ == self.__class:
                self.__online_beta = online_beta
                break
        dprint("choosing online beta ", self.__online_beta)

    def scenario_offline_beta(self, *classes):
        options = [(t[0], float(t[1])) for t in (s.split(":") for s in classes)]
        for class_, offline_beta in options:
            if class_ == self.__class:
                self.__offline_beta = offline_beta
        dprint("choosing offline beta ", self.__offline_beta)

    def scenario_expon_churn(self):
        return super(ScenarioScript, self).scenario_expon_churn(self.__online_beta, self.__offline_beta)

    def scenario_end(self):
        EffortCommunity.flush_log()
        return "END"
