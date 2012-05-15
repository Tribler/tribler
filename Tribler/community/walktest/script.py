from community import WalktestCommunity, DAS2SCENARIO, DAS4SCENARIO
from lencoder import close, bz2log
from Tribler.dispersy.tool.scenarioscript import ScenarioScript

if DAS2SCENARIO:
    class ScenarioScript(ScenarioScript):
        @property
        def master_member_public_key(self):
            return "3081a7301006072a8648ce3d020106052b81040027038192000400b8856992e117d129d58de020ed24f5dd2bad18fb7dcf93c3e7615b005280673c51a11fefa475d549928d8d4cb2307ceea17c754f31a3413517aee41ac3190da2ef772ba4de8e6b04b8846520b0f59f840bac3a12c169a4e77904bc1d46f80740308076433bcda641e2effb43d5ce6af9655751a617abdcf43905b4fc7bec4e74de5866bbd7c0de358617c59064451a".decode("HEX")

        @property
        def community_class(self):
            return WalktestCommunity

        def scenario_end(self):
            bz2log("walktest.log", "scenario-end")
            close("walktest.log")
            return "END"

        def log(self, _message, **kargs):
            bz2log("walktest.log", _message, **kargs)

if DAS4SCENARIO:
    from Tribler.dispersy.tool.scenarioscript import ScenarioExpon, ScenarioUniform

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
