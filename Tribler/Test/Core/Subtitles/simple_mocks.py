# Written by Andrea Reale
# see LICENSE.txt for license information

import logging
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.Subtitles.MetadataDomainObjects.SubtitleInfo import SubtitleInfo
from Tribler.Core.Subtitles.MetadataDomainObjects.MetadataDTO import MetadataDTO
import time
import os.path
from Tribler.Core.Utilities.Crypto import sha

RES_DIR = os.path.join('..','..','subtitles_test_res')




log = logging.getLogger(__name__)

class MockOverlayBridge(object):

    def __init__(self):
        self.send_count = 0
        self.sendParametersHistory = list()
        self.connect_count = 0
        self.connectParametersHistory = list()
        self.add_task_count = 0
        self.add_taskParametersHistory = list()

    def send(self,permid,msg,callback):
        log.debug("MockBridge: Message " + msg + " sent to " +
                  show_permid_short(permid))
        self.send_count += 1
        self.sendParametersHistory.append((permid,msg,callback))
        callback(None, permid)

    def connect(self,permid,callback):
        log.debug("MockBridge: Connected to " +
                  show_permid_short(permid))
        self.connect_count += 1
        self.connectParametersHistory.append((permid,callback))
        callback(None, None, permid, 14)

    def add_task(self, task, t=0):
        log.debug("MockBridge: added task %s to be scheduled in %d seconds" %
                  (str(task), t))
        self.add_task_count += 1
        self.add_taskParametersHistory.append((task,t))



class ConnectedMockOverlayBridge(MockOverlayBridge):
    def __init__(self):
        self.ol_connection = None



    def send(self,permid,msg,callback):
        if self.ol_connection is not None:
            self.ol_connection.send(msg)
        super(ConnectedMockOverlayBridge, self).send(self,permid,msg,callback)

class MockTokenBucket:

    def __init__(self):
        self.sufficientTokens = True

    def consume(self,howManyTokens):
        return self.sufficientTokens


class MockMetadataDBHandler(object):

    def __init__(self):

        self.returnMetadata = True
        self.getAllSubsCount = 0
        self.getAllSubsParametersHistory = list()

        self.getMetadataCount = 0
        self.getMetadataParametesHistory = list()

        self.updateSubtitleCount = 0
        self.updateSubtitleParameterHistory = list()

        self.commitCount = 0

        s1 = SubtitleInfo("eng", os.path.join(RES_DIR,"fake0.srt"))
        s1.computeChecksum()
        s2 = SubtitleInfo("rus", os.path.join(RES_DIR,"fake1.srt"))
        s2.computeChecksum()

        self.returnSubs = {
                            "eng" : s1,
                            "rus" : s2
                            }

        self.insertMetadataCount = 0
        self.insertMetadataParameters = list()
        self.nextKeypair = None


    def getAllSubtitles(self, channel_id, infohash):
        self.getAllSubsCount += 1
        self.getAllSubsParametersHistory.append((channel_id, infohash))
        return self.returnSubs

    def getMetadata(self,channel_id,infohash):

        self.getMetadataCount += 1
        self.getMetadataParametesHistory.append((channel_id, infohash))
        if self.returnMetadata:
            return self.getSomeMetadata(channel_id,infohash)
        else:
            return None


    def getSomeMetadata(self, channel_id, infohash):


        s1 = SubtitleInfo("eng", None)
        s2 = SubtitleInfo("rus", None)

        self.content1 = u"Subtitle Content 1"
        self.content2 = u"Subtitle Content 2"

        hasher = sha()
        hasher.update(self.content1)
        s1.checksum = hasher.digest()

        hasher = sha()
        hasher.update(self.content2)
        s2.checksum = hasher.digest()

        metadata = MetadataDTO(channel_id, infohash, time.time(),
                               "", {"eng":s1, "rus":s2})

        if self.nextKeypair is None:
            metadata.signature = "fake"
        else:
            metadata.sign(self.nextKeypair)

        return metadata

    def updateSubtitlePath(self, channel_id, infohash, lang, newPath, commitNow):
        self.updateSubtitleCount += 1
        self.updateSubtitleParameterHistory.append((channel_id,infohash,
                                                    lang, newPath, commitNow))
        return True

    def commit(self):
        self.commitCount += 1

    def insertMetadata(self,metadataDTO):
        self.insertMetadataCount += 1
        self.insertMetadataParameters.append((metadataDTO,))
        return True



class MockVoteCastHandler(object):

    def __init__(self):
        self.nextVoteValue = 0

        self.getVoteCount = 0
        self.getVoteParametersHistory = list()

    def getVote(self,channel,permid):
        self.getVoteCount += 1
        self.getVoteParametersHistory.append((channel,permid))
        return self.nextVoteValue

class MockSubtitlesHandler(object):

    def __init__(self):
        self.sendSubReqCount = 0
        self.sendSubReqParametersHistory = list()

        self.retrieveMultipleCount = 0
        self.retrieveMultipleParams = list()

    def sendSubtitleRequest(self, dest, channel, infohash,lang, callback = None):
        self.sendSubReqCount += 1
        self.sendSubReqParametersHistory.append((dest,channel,infohash,lang,callback))

    def retrieveMultipleSubtitleContents(self, channel, infohash, listOfSubInofs, callback=None):
        self.retrieveMultipleCount += 1
        self.retrieveMultipleParams.append((channel,infohash,listOfSubInofs,callback))




class MockLaunchMany(object):
    def __init__(self):
        self.set_act_count = 0
        self.set_act_count_param_history= list()
        self.richmetadataDbHandler = MockMetadataDBHandler()

    def set_activity(self,activity,param):
        self.set_act_count += 1
        self.set_act_count_param_history.append((activity,param))


class MockMsgListener(object):
    def __init__(self):
        self.receivedCount = 0
        self.receivedParams = list()
        self.subsCount = 0
        self.subsParams = list()

    def receivedSubsRequest(self,permid,decoded,selversion):
        self.receivedCount += 1
        self.receivedParams.append((permid,decoded,selversion))

    def receivedSubsResponse(self, permid, decoded, callbacks, selversion):
        self.subsCount += 1
        self.subsParams.append((permid,decoded,callbacks,selversion))

class MockSubsMsgHander(object):
    def __init__(self):
        self.sendReqCount = 0
        self.sendReqParams = list()

        self.sendResCount = 0
        self.sendResParams = list()

    def sendSubtitleRequest(self, dest_permid, requestDetails,
                            msgSentCallback = None, userCallback = None, selversion=-1):
        self.sendReqCount += 1
        self.sendReqParams.append((dest_permid,requestDetails,msgSentCallback, userCallback, selversion))

    def sendSubtitleResponse(self, destination, response_params,
                             selversion = -1):
        self.sendResCount += 1
        self.sendResParams.append((destination,response_params,selversion))

class MockPeersHaveMngr(object):

    def __init__(self):
        self.getPeersHavingCount = 0
        self.getPeersHavingParams = list()

        self.newHaveCount = 0
        self.newHaveParams = list()

        self.retrieveCount = 0
        self.retrieveParams = list()

        self.cleanupCount = 0

    def getPeersHaving(self, channel, infohash, bitmask, limit=5):
        self.getPeersHavingCount += 1
        self.getPeersHavingPars.pars((channel,infohash,bitmask,limit))

        return ["permid1","permid2","permid3"]


    def newHaveReceived(self, channel, infohash, peer_id, havemask):
        self.newHaveCount += 1
        self.newHaveParams.append((channel, infohash, peer_id, havemask))


    def retrieveMyHaveMask(self, channel, infohash):
        self.retrieveCount += 1
        self.retrieveParams.append((channel, infohash))

        return 42


    def startupCleanup(self):
        self.cleanupCount += 1

class MockSession(object):
    '''
    only implements methods to read the config
    '''



    def get_state_dir(self):
        return os.path.join(RES_DIR,'state')

    def get_subtitles_collecting_dir(self):
        return "subtitles_collecting_dir"

    def get_subtitles_upload_rate(self):
        return 1024
