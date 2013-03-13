#Written by Niels Zeilemaker
from Tribler.dispersy.member import Member
from Tribler.dispersy.script import ScenarioScriptBase
from Tribler.community.demers.community import DemersTest
from Tribler.dispersy.tool.lencoder import log
from random import choice
from string import letters

class DemersScript(ScenarioScriptBase):
    def __init__(self, **kargs): #, script, name, **kargs):
        ScenarioScriptBase.__init__(self, 'barter.log', **kargs)
    
    def join_community(self, my_member):
        self.my_member = my_member
        
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404f10c33b03d2a09943d6d6a4b2cf4fe3129e5dce1df446a27d0ce00d48c845a4eff8102ef3becd6bc07c65953c824d227ebc110016d5ba71163bf6fb83fde7cdccf164bb007e27d07da952c47d30cf9c843034dc7a4603af3a84f8997e5d046e6a5f1ad489add6878898079a4663ade502829577c7d1e27302a3d5ea0ae06e83641a093a87465fdd4a3b43e031a9555".decode("HEX")
        master = Member(master_key)
        
        community = DemersTest.join_community(master, self.my_member)
        return community
    
    def execute_scenario_cmds(self, commands):
        for command in commands:
            cur_command = command.split()
            if cur_command[0] == 'publish':
                log(self._logfile, "creating-text")
                text = u''.join(choice(letters) for _ in xrange(100))
                self._community.create_text(text)
