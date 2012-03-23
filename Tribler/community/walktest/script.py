from community import WalktestCommunity
from lencoder import close, bz2log

from Tribler.Core.dispersy.tool.scenarioscript import ScenarioScript, ScenarioExpon, ScenarioUniform

class ScenarioScript(ScenarioScript, ScenarioExpon, ScenarioUniform):
    @property
    def master_member_public_key(self):
        return "3081a7301006072a8648ce3d020106052b810400270381920004008be5c9f62d949787a3470e3ed610c30eab479ae3f4e97af987ea2c25f68a23ff3754d0e59f22839444479e6d0e4db9e8e46752d067b0764388a6a174511950fb66655a65f819fc065de7c383477a1c2fecdad0d18e529b1ae003a4c6c7abf899bd301da7689dd76ce248042477c441be06e236879af834f1def7c7d9848d34711bf1d1436acf00239f1652ecc7d1cb".decode("HEX")

    @property
    def community_class(self):
        return WalktestCommunity

    def scenario_end(self):
        bz2log("walktest.log", "scenario-end")
        close("walktest.log")
        return "END"

    def log(self, _message, **kargs):
        bz2log("walktest.log", _message, **kargs)
