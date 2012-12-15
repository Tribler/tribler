from random import choice
from string import letters
from time import time

from community import AllChannelCommunity
from Tribler.community.channel.community import ChannelCommunity
from Tribler.community.channel.preview import PreviewChannelCommunity

from Tribler.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin
from Tribler.dispersy.member import Member
from Tribler.dispersy.script import ScriptBase
from Tribler.dispersy.debug import Node
from Tribler.dispersy.dprint import dprint
from Tribler.dispersy.tool.lencoder import log

from Tribler.dispersy.script import ScenarioScriptBase
    
class AllChannelScenarioScript(ScenarioScriptBase):
    def __init__(self, **kargs):
        ScenarioScriptBase.__init__(self, 'barter.log', **kargs)
        
        self.my_channel = None
        self.joined_community = None
        self.want_to_join = False
        self.torrentindex = 1

        self._dispersy.define_auto_load(ChannelCommunity, (), {"integrate_with_tribler":False})
        self._dispersy.define_auto_load(PreviewChannelCommunity)
        
    def join_community(self, my_member):
        self.my_member = my_member
        
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403cbbfd2dfb67a7db66c88988df56f93fa6e7f982f9a6a0fa8898492c8b8cae23e10b159ace60b7047012082a5aa4c6e221d7e58107bb550436d57e046c11ab4f51f0ab18fa8f58d0346cc12d1cc2b61fc86fe5ed192309152e11e3f02489e30c7c971dd989e1ce5030ea0fb77d5220a92cceb567cbc94bc39ba246a42e215b55e9315b543ddeff0209e916f77c0d747".decode("HEX")
        master = Member(master_key)

        return AllChannelCommunity.join_community(master, self.my_member, self.my_member, integrate_with_tribler = False)
    
    def execute_scenario_cmds(self, commands):
        torrents = []
        
        for command in commands:
            cur_command = command.split()
        
            if cur_command[0] == 'create':
                log(self._logfile, "creating-community")
                self.my_channel = ChannelCommunity.create_community(self.my_member, integrate_with_tribler = False)
                
                log(self._logfile, "creating-channel-message")
                self.my_channel.create_channel(u'', u'')
            
            elif cur_command[0] == 'publish':
                if self.my_channel:
                    infohash = str(self.torrentindex)
                    infohash += ''.join(choice(letters) for _ in xrange(20-len(infohash)))
                    
                    name = u''.join(choice(letters) for _ in xrange(100))
                    files = []
                    for _ in range(10):
                        files.append((u''.join(choice(letters) for _ in xrange(30)), 123455))
                    
                    trackers = []
                    for _ in range(10):
                        trackers.append(''.join(choice(letters) for _ in xrange(30))) 
                    
                    files = tuple(files)
                    trackers = tuple(trackers)
                    
                    self.torrentindex += 1
                    torrents.append((infohash, int(time()), name, files, trackers))
            
            elif cur_command[0] == 'post':
                if self.joined_community:
                    text = ''.join(choice(letters) for i in xrange(160))
                    self.joined_community._disp_create_comment(text, int(time()), None, None, None, None)
                
            elif cur_command[0] == 'join':
                self.want_to_join = True
                
        if self.want_to_join:
            from Tribler.dispersy.dispersy import Dispersy
            dispersy = Dispersy.get_instance()
            
            log(self._logfile, "trying-to-join-community")
            
            cid = self._community._channelcast_db.getChannelIdFromDispersyCID(None)
            if cid:
                community = self._get_channel_community(cid)
                if community._channel_id:
                    self._community.disp_create_votecast(community.cid, 2, int(time()))
                    
                    log(self._logfile, "joining-community")
                    self.joined_community = community
                    
                    self.want_to_join = False
                    break
                
        if len(torrents) > 0:
            log(self._logfile, "creating-torrents")
            self.my_channel._disp_create_torrents(torrents)
