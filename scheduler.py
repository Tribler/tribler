import sys
import wx
import os

from random import shuffle
from shutil import move, copy2
from threading import Event, Thread
from time import time
from threading import Timer
from traceback import print_exc
from cStringIO import StringIO

from BitTornado.bencode import *

from interconn import ClientPassParam
from abctorrent import ABCTorrent

from Utility.compat import *
from Utility.constants import *

wxEVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)
    
def DELEVT_INVOKE(win):
    win.Disconnect(-1, -1, wxEVT_INVOKE)

class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        wx.PyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs

#wxEVT_SCH = wx.NewEventType()
#
#def EVT_SCH(win, func):
#    win.Connect(-1, -1, wxEVT_SCH, func)
#
#class SchEvent(wx.PyEvent):
#    def __init__(self, func, args, kwargs):
#        wx.PyEvent.__init__(self)
#        self.SetEventType(wxEVT_SCH)
#        self.func = func
#        self.args = args
#        self.kwargs = kwargs

# Separate out some of the methods that are solely used to
# deal with actions that occur in ABCList
class ActionHandler:
    def __init__(self, utility):
        self.utility = utility
        self.queue = self.utility.queue

    def procREMOVE(self, workinglist = [], removefiles = False):
        indexremoved = []
        for ABCTorrentTemp in workinglist:
            indexremoved.append(ABCTorrentTemp.listindex)
            
            if self.utility.config.Read('removetorrent', "boolean"):
                try:
                    os.remove(ABCTorrentTemp.src)
                except:
                    pass

            ABCTorrentTemp.shutdown()
            
            if removefiles:
                ABCTorrentTemp.removeFiles()
            
            ABCTorrentTemp = None

        # Only need to update if we actually removed something
        if len(indexremoved) > 0:
            indexremoved.sort()
            indexremoved.reverse()
            for index in indexremoved:
                # Remove from the display
                self.utility.list.DeleteItem(index)
            
                # Remove from scheduler
                self.queue.proctab.pop(index)

            self.queue.updateListIndex(startindex = indexremoved[-1])
            self.queue.updateAndInvoke()

    def procMOVE(self, workinglist = None):
        if workinglist is None:
            workinglist = self.queue.proctab
            
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.move()
            if change:
                update = True
            
        if update:
            self.queue.updateAndInvoke()

    def procSTOP(self, workinglist = None):
        if workinglist is None:
            workinglist = self.queue.proctab
            
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.actions.stop()
            if change:
                update = True
            
        if update:
            self.queue.updateAndInvoke()

    def procUNSTOP(self, workinglist = None):
        if workinglist is None:
            workinglist = self.queue.proctab

        update = False
        for ABCTorrentTemp in self.queue.proctab:
            if ABCTorrentTemp.status['value'] == STATUS_STOP:
                change = ABCTorrentTemp.actions.queue()
                if change:
                    update = True

        if update:
            self.queue.updateAndInvoke()
        
    def procPAUSE(self, workinglist = None, release = False):       
        if workinglist is None:
            workinglist = self.queue.activetorrents
        
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.actions.pause(release)
            if change:
                update = True

        if update:
            self.queue.UpdateRunningTorrentCounters()
       
    def procRESUME(self, workinglist = None):
        if workinglist == None:
            workinglist = self.queue.proctab
        
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.actions.resume()
            if change:
                update = True

        if update:
            self.queue.updateAndInvoke(invokeLater = False)

    def procQUEUE(self, workinglist = None):
        if workinglist == None:
            workinglist = self.queue.proctab
            
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.actions.queue()
            if change:
                update = True
        
        if update:
            self.queue.updateAndInvoke()

    def procHASHCHECK(self, workinglist = None):
        if workinglist == None:
            workinglist = self.queue.proctab
            
        update = False
        for ABCTorrentTemp in workinglist:
            change = ABCTorrentTemp.actions.hashCheck()
            if change:
                update = True
        
        if update:
            self.queue.updateAndInvoke()

class RateManager(wx.EvtHandler):
    def __init__(self, utility):
        wx.EvtHandler.__init__(self)
               
        self.utility = utility
        self.queue = utility.queue

        # For Upload Rate Maximizer
        # Time when the upload rate is lower than the URM threshold for the first time
        # This is used to trigger the start of a torrent by the URM only after a certain amount
        # of time of exceeding of the threshold

        # Time when the upload rate is greater than the global max upload rate for the first time
        # This is used to trigger the stop of a torrent by the URM only after a certain amount of
        # time of exceeding of the threshold
        self.urm_time = { 'under' : 0.0, 
                          'over'  : 0.0 }
        
        # Counts the number of times the same torrent is started in a row by the URM
        self.laststartedtorrentcounter = 0
        
        # Id of the last torrent started by the URM
        self.laststartedtorrent = None

        # Time counter used :
        #     - to delay the torrent managing by the URM just after ABC starts.
        #     - to leave a minimum of urmdelay seconds between the starting of 2 torrents in a row by the URM
        self.urmstartingtime = 0

        # bandwidth between reserved up rate and measured up rate over which a torrent will have its reserved up rate lowered
        self.calcupth1 = 2.3
        # bandwidth between reserved up rate and measured up rate under which a torrent will have its reserved up rate raised
        self.calcupth2 = 0.7
        self.meancalcupth = (self.calcupth1 + self.calcupth2) / 2

        # Flag that stays True as long as, just after ABC starts, there are still torrents in "checking existing" status.
        # This is used to prevent the URM to start unnecessary torrents when due to run torrents are not yet started.
        self.abcstarting = True

        self.flag = Event()
        EVT_INVOKE(self, self.onInvoke)

    def onInvoke(self, event):
        if not self.flag.isSet():
            event.func(*event.args, **event.kwargs)
#        else:
#            sys.stderr.write("oninvoke: flag is set\n")

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.flag.isSet():
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))
#        else:
#            sys.stderr.write("invokelater: flag is set\n")
                
    def RunTasks(self):
        self.invokeLater(self.RateTasks)
            
    def RateTasks(self):
        self.flag.set()
        
        self.utility.queue.urmdistribrunning = True
        
        self.UploadRateMaximizer()
        
        self.CalculateBandwidth("down")
        self.CalculateBandwidth("up")
        
        self.utility.queue.urmdistribrunning = False
        
        self.flag.clear()
        
    def CalculateBandwidth(self, dir = "up"):
        # No active file, not need to calculate
        if dir == "up":
            if (self.queue.counters['downloading'] + self.queue.counters['seeding']) == 0:
                return       
        else:
            if self.queue.counters['downloading'] == 0:
                return
        
        maxrate = self.MaxRate(dir)
        # See if global rate settings are set to unlimited
        if maxrate == 0:
            # Unlimited rate
            for ABCTorrentTemp in self.queue.activetorrents:
                ABCTorrentTemp.maxrate[dir] = str(ABCTorrentTemp.getLocalRate(dir))
#                if ABCTorrentTemp.useLocalRate(dir):
#                    ABCTorrentTemp.maxrate[dir] = ABCTorrentTemp.maxlocalrate[dir]
#                else:
#                    ABCTorrentTemp.maxrate[dir] = "0"
            self.distributeBandwidth(dir = dir)
            return
        
        #print "====================== BEGINNING ALGO ======= th1=%.1f ; th2=%.1f =============================" % (self.calcupth1, self.calcupth2)

        #######################################################
        # - Find number of completed/incomplete torrent
        # - Number of torrent using local setting
        # - Upload bandwidth already used by torrents
        # - Sorting of torrents in lists according to their will in matter of upload rate :
        #   (tobelowered, toberaisedinpriority, toberaised, nottobechanged)
        #######################################################

        # In all the following descriptions, id stands for the unique identifier of a torrent ; this is not the index in the torrent list.
        localprioactive = []      # ids and upload rate for torrents with local upload rate settings when prioritizelocal is set (see prioritizelocal)
        allactive = []            # list index, id and measured up rate for active torrents
        tobelowered = []          # ids for running torrents for which measured up rate is lowering and so reserved upload rate can be lowered
        toberaised = []           # ids for running torrents for which measured up rate is growing and so reserved upload rate can be raised,
                                  # and with reserved up rate > 3 kB/s
        toberaisedinpriority = [] # ids for running torrents for which reserved upload rate can be raised, with reserved up rate < 3 kB/s
                                  # These will always be raised even there's no available up bandwith, to fulfill the min 3 kB/s up rate rule
        nottobechanged = []       # ids for running torrents for which reserved up rate is not to be changed and is > 3kB/s ; (for these, the
                                  # measured up rate is between (max upload reserved - self.calcupth1) and (max upload reserved - self.calcupth2)
        meanrate = 0.0          # mean max upload rate for torrents to be raised or not to be changed ; it will be used to decide which torrents
                                  # must be raised amongst those that want to get higher and that must share the available up bandwidth. The torrents
                                  # that don't want to change their up rate and that are below 3 kB/s are not taken into account on purpose, because
                                  # these ones will never be lowered to give more up rate to a torrent that wants to raise its up rate, or to
                                  # compensate for the up rate given to torrents to be raised in priority.

        
        self.moveinlistdetected = False
        usedupbandwidth = 0

        prioritizelocal = self.utility.config.Read('prioritizelocal')
                                  # Option set in Preferences/Queue.
                                  # If not set, torrents with upload rate local settings are treated like other torrents, except they have their
                                  # own max upload rate they can't cross over. The consequence is a behaviour slightly different from the behavior of
                                  # ABC releases prior to 2.7.0.
                                  # If set, this gives the algorithm the behaviour of ABC releases prior to 2.7.0 : the torrents with an upload rate
                                  # local setting will be granted upload bandwidth in priority to fulfill their local setting, even is this one
                                  # is higher than the global max upload rate setting, and even if this bandwidth must be taken from other active
                                  # torrents wihout a local upload rate setting. These torrents will not take part in the upload rate exchange
                                  # between active torrents when all bandwidth has been distributed, since they will have been served in priority.
        
        # Build lists for URM  and non URM with up > 3kB/s, and for all URM. These lists exclude torrents with local upload settings
        # if prioritizelocal is set.
        # These lists will be used in Phase 2 bis
        nonurmtoberaised = []     # ids for torrents not started by the URM and with reserved up rate > 3 kB/s
        urmtoberaised = []                  # ids for active torrents started by the URM and with reserved up rate > 3 kB/s
               
        for ABCTorrentTemp in self.queue.activetorrents:
            # Active Torrent
            if ((dir != "down" or not ABCTorrentTemp.status['completed'])
                and ABCTorrentTemp.abcengine_adr is not None
                and ABCTorrentTemp.abcengine_adr.hasConnections
                and ABCTorrentTemp.status['value'] != STATUS_PAUSE):

                rate = self.utility.size_format(ABCTorrentTemp.abcengine_adr.rate[dir], stopearly = "KB", rawsize = True)

                allactive.append((ABCTorrentTemp, rate))
                usedupbandwidth += rate
                maxrate_float = float(ABCTorrentTemp.maxrate[dir])

                # Torrents dispatch
                if prioritizelocal == '1' and ABCTorrentTemp.getLocalRate(dir, True):
                    localprioactive.append((ABCTorrentTemp, rate))
                elif rate < 0.05:
                    # These are the torrents that don't want to have their up rate changed and that have an allmost null up rate
                    # They will not go lower, we can reset their reserved up rate until they want to get higher
                    ABCTorrentTemp.maxrate[dir] = "0"
                elif maxrate_float - rate > self.calcupth1:
                    tobelowered.append((ABCTorrentTemp, rate))
                elif maxrate_float - rate <= self.calcupth2:
                    if rate < 3:
                        toberaisedinpriority.append((ABCTorrentTemp, rate))
                    else:
                        toberaised.append((ABCTorrentTemp, rate))
                        if dir == "up" and ABCTorrentTemp in self.queue.urmtorrents:
                            urmtoberaised.append(ABCTorrentTemp)
                        else:
                            nonurmtoberaised.append((ABCTorrentTemp, rate))
                        meanrate += maxrate_float
                elif rate > 3:
                    nottobechanged.append((ABCTorrentTemp, rate))
                    if dir == "up" and ABCTorrentTemp in self.queue.urmtorrents:
                        urmtoberaised.append(ABCTorrentTemp)
                    meanrate += maxrate_float

                    #print "index: %i ; rate: %.1f ; reserved: %.1f ; maxlocal: %.1f" % (ABCTorrentTemp.listindex, \
                    #      rate, maxrate_float, float(ABCTorrentTemp.maxlocalrate[dir]))

        ###############################################
        # Calculate upload rate for each torrent
        ###############################################
        
        availableratetobedistributed = maxrate
        
        if ((availableratetobedistributed != 0)
            and (1 - (usedupbandwidth / availableratetobedistributed) > 0.20)):
            self.distributeFreeWheeling(allactive, dir = dir)
            return

        ###########################################################################
        # First treat special torrents before going on sharing and distributing
        ###########################################################################

        # Treat in priority the torrents with up rate below 3 kB/s and that want to get a higher rate
        grantedfortoberaisedinpriority = 0.0
        for t in toberaisedinpriority:
            ABCTorrentTemp = t[0]
            newreservedrate = t[1] + self.meancalcupth
            if newreservedrate > 3:
                grantedfortoberaisedinpriority += 3 - float(ABCTorrentTemp.maxrate[dir])
                ABCTorrentTemp.maxrate[dir] = '3'
            else:
                grantedfortoberaisedinpriority += newreservedrate - float(ABCTorrentTemp.maxrate[dir])
                ABCTorrentTemp.maxrate[dir] = str(newreservedrate)

        grantedforlocalprioactive = self.distributePrioritizeLocal(localprioactive, dir = dir)

        # Torrents that want to be lowered in upload rate (and give back some reserved upload bandwidth)
        givenbackbytobelowered = 0
        for t in tobelowered:
            ABCTorrentTemp = t[0]
            newreservedrate = t[1] + self.meancalcupth
            givenbackbytobelowered += newreservedrate - float(ABCTorrentTemp.maxrate[dir])
            ABCTorrentTemp.maxrate[dir] = str(newreservedrate)
        
        # Add to available upload rate to be distributed the up rate given back by the torrents that have been lowered ;
        # Substract from available upload rate the up rate used for each torrent that have been be raised in priority (torrents with up rate
        # below 3 kB/s and that want to get higher).
        availableratetobedistributed += givenbackbytobelowered - grantedfortoberaisedinpriority - grantedforlocalprioactive - usedupbandwidth
        #print "availableratetobedistributed is %.3f" % availableratetobedistributed

        # localprioactive torrents have already been updated if prioritizelocal is set
        toberegulated = [t[0] for t in allactive if t not in localprioactive]

        #print "nonurm =", nonurm
        #print "nonurmtoberaised =", nonurmtoberaised
        #print "urmtoberaised =", urmtoberaised

        # There's nothing to do if no torrent want to be raised
        if len(toberaised) == 0:
            ################################################
            # Set new max upload rate to all active torrents
            ################################################
            self.distributeBandwidth(toberegulated, dir = dir)
            return
               
        if availableratetobedistributed > 0:
            ###########################################################################
            #print "PHASE 1"
            ###########################################################################
            # Phase 1 : As long as there's available upload bandwidth below the total max to be distributed, I give some
            # to any torrents that asks for it.
            # There's a special case with torrents to be raised that have a local max up rate : they must be topped to their max local
            # up rate and the surplus part of the reserved bandwidth may be reused.
            # To sum up : In Phase 1, the measured up rate is leading the reserved up rate.

            # Check if all torrents that claim a higher reserved up rate will be satisfied
            claimedrate = 0
            for t in toberaised:
                ABCTorrentTemp = t[0]
                maxup = float(ABCTorrentTemp.maxrate[dir])
                newreservedrate = t[1] + self.meancalcupth
                toadd = newreservedrate

                maxlocalup = float(ABCTorrentTemp.getLocalRate(dir))
#                if ABCTorrentTemp.useLocalRate(dir):
#                    maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
                if maxlocalup > 0 and newreservedrate > maxlocalup:
                    toadd = maxlocalup
                
                claimedrate += toadd - maxup

            #print "Claimed up rate :", claimedrate
            #print "Available up rate :", availableratetobedistributed

            if claimedrate <= availableratetobedistributed:
                realupfactor = 1
            else:
                realupfactor = availableratetobedistributed / claimedrate

            # If all claims can be fulfilled ; we distribute and go to end.
            # If there's not enough remaining up rate to fulfill all claims, the remaining available up rate will be
            # distributed proportionally between all torrents that want to raise.
            for t in toberaised:
                ABCTorrentTemp = t[0]
                maxup = float(ABCTorrentTemp.maxrate[dir])
                newreservedrate = t[1] + self.meancalcupth
                newmaxup = maxup + (newreservedrate - maxup) * realupfactor

                maxlocalup = float(ABCTorrentTemp.getLocalRate(dir))
#                if ABCTorrentTemp.useLocalRate(dir):
#                    maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
#                    if newreservedrate > maxlocalup:
                if maxlocalup > 0 and newreservedrate > maxlocalup:
                    newmaxup = maxup + (maxlocalup - maxup) * realupfactor

                ABCTorrentTemp.maxrate[dir] = str(newmaxup)
                #print "index :", ABCTorrentTemp.listindex, "; up rate raised from", maxup, "to", ABCTorrentTemp.maxrate[dir]
            
            ################################################
            # Set new max upload rate to all active torrents
            ################################################
            self.distributeBandwidth(toberegulated, dir = dir)
            return

        ###########################################################################
        #print "PHASE 2"
        ###########################################################################
        # -a- Each torrent that wants its up rate to be raised or not to be changed will have its reserved up rate lowered
        #     to compensate the bandwidth given in priority to torrents with up rate below 3 kB/s and torrents with local up rate
        #     settings if "prioritize local" is set. This lowering must not bring the reserved up rate of a torrent below 3 kB/s.
        #     Torrents will be sorted by their reserved up rate and treated from the lower to the bigger. If a part of the lowering
        #     cannot be achieved with a torrent,it will be dispatched to the pool of the remaining torrents to be treated.
        #     After this, there may still be more total up rate reserved than available up rate because of the min 3 kB/s rule.
        ###########################################################################

        # -a-
        if availableratetobedistributed < 0:
            rate_id = []
            pooltobelowered = toberaised + nottobechanged
            for t in pooltobelowered:
                if t[1] > 3:
                    # a "to be raised" torrent may have its old reserved up rate below 3
                    # These ones cannot give anything, they are skipped
                    rate_id.append((float(t[0].maxrate[dir]), t[0]))
            sizerate_id = len(rate_id)
            # Sort by increasing reserved up rate
            rate_id.sort()
            if sizerate_id:
                ratenotassignedforeach = availableratetobedistributed / sizerate_id
            # Compute new reserved up rate
            i = 0
            for t in rate_id:
                # (availableratetobedistributed and ratenotassignedforeach are negative numbers)
                newmaxrate = t[0] + ratenotassignedforeach
                i += 1
                if newmaxrate < 3:
                    # if some up rate lowering could not be dispatched, it will be distributed to the next torrents
                    # in the list (which are higher in max up rate because the list is sorted this way)
                    if sizerate_id and i != sizerate_id:
                        ratenotassignedforeach += (newmaxrate - 3) / (sizerate_id - i)
                    newmaxrate = 3
                t[1].maxrate[dir] = str(newmaxrate)
            #    print "%i lowered from %.3f to %.3f" % (t[1].listindex, t[0], newmaxrate)
            #print "availableratetobedistributed is now %.3f" % availableratetobedistributed


        if (self.utility.config.Read('urmlowpriority') == "0"
             or not (urmtoberaised and nonurmtoberaised)):
            ###########################################################################
            #print "PHASE 2 algo with mean upload rate"
            ###########################################################################
            # Phase 2 : There's no more available upload bandwidth to be distributed, I split the total max between active torrents.
            # -b- Compute the mean max upload rate for the pool of torrents that want their up rate to be raised or not to be changed
            #     and list torrents below and above that mean value.
            # -c- The regulation for torrents that want to have their upload rate raised is computed this way :
            #     The idea is to target a mean upload rate for all torrents that want to raise their up rate or don't want to have it
            #     changed, taking into account the max up rates of local settings, and the fact that no torrent must be lowered down below
            #     3 kB/s.
            # To sum up : In Phase 2, the reserved up rate is leading the real up rate .

            # -b-
            # Mean reserved up rate calculation
            # If prioritizelocal is set, all torrents with a local up rate settting are completely excluded from
            # the upload bandwidth exchange phase between other torrents. This is because this phase
            # targets a mean upload rate between torrents that want to upload more, and when prioritizelocal
            # is set, torrents with a local up rate settting can be very far from this mean up rate and their
            # own purpose is not to integrate the pool of other torrents but to live their own life (!)

            if toberaised or nottobechanged:
                meanrate /= len(toberaised) + len(nottobechanged)
            #print "Mean up rate over 3 kB/s : %.1f" % meanrate

            raisedbelowm = []         # ids for torrents to be raised and with reserved up rate below mean max upload rate
            allabovem = []            # ids for torrents to be raised or not to be changed and with reserved up rate above mean max upload rate
            
            for t in toberaised:
                maxrate_float = float(t[0].maxrate[dir])
                if maxrate_float > meanrate:
                    allabovem.append(t)
                elif maxrate_float < meanrate:
                    raisedbelowm.append(t)
            for t in nottobechanged:
                if float(t[0].maxrate[dir]) > meanrate:
                    allabovem.append(t)

            # -c-
            if raisedbelowm and allabovem:
                # Available bandwidth exchange :
                up = 0.0
                down = 0.0
                for t in raisedbelowm:
                    ABCTorrentTemp = t[0]
                    toadd = meanrate - float(ABCTorrentTemp.maxrate[dir])

                    maxlocalrate_float = float(ABCTorrentTemp.getLocalRate(dir))
#                    if ABCTorrentTemp.useLocalRate(dir):
#                        maxlocalrate_float = float(ABCTorrentTemp.maxlocalrate[dir])
#                        if maxlocalrate_float <= meanrate:
                    if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                        toadd = maxlocalrate_float - float(ABCTorrentTemp.maxrate[dir])
                    up += toadd
                for t in allabovem:
                    down += float(t[0].maxrate[dir]) - meanrate
                if up > down:
                    limitup = down / up                        
                
                # Speed up slow torrents that want their up rate to be raised :
                # Each one must have its reserved up rate raised slowly enough to let it follow this raise if it really
                # wants to get higher. If we set the reserved to the max in one shot, these torrents will be then detected
                # in the next phase 1 as to be lowered, which is not what we want.
                realup = 0.0
                for t in raisedbelowm:
                    ABCTorrentTemp = t[0]
                    maxup = float(ABCTorrentTemp.maxrate[dir])
                    toadd = meanrate - maxup

#                    if ABCTorrentTemp.useLocalRate(dir):
#                        maxlocalrate_float = float(ABCTorrentTemp.maxlocalrate[dir])
#                        if maxlocalrate_float <= meanrate:
                    maxlocalrate_float = float(ABCTorrentTemp.getLocalRate(dir))
#                    if ABCTorrentTemp.useLocalRate(dir):
#                        maxlocalrate_float = float(ABCTorrentTemp.maxlocalrate[dir])
#                        if maxlocalrate_float <= meanrate:
                    if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                        toadd = maxlocalrate_float - maxup

                    if up > down:
                        toadd *= limitup
                    # step is computed such as if the torrent keeps on raising at the same rate as before, it will be
                    # analysed as still wanting to raise by the next phase 1 check
                    step = 2 * (t[1] + self.calcupth2 - maxup)
                    if toadd < step:
                        ABCTorrentTemp.maxrate[dir] = str(maxup + toadd)
                        realup += toadd
                    else:
                        ABCTorrentTemp.maxrate[dir] = str(maxup + step)
                        realup += step
                    #print "index :", t[0].listindex, "; up rate raised from", maxup, "to", ABCTorrentTemp.maxrate[dir]          
                realup /= len(allabovem)
                # Slow down fast torrents :
                for t in allabovem:
                    maxup = float(t[0].maxrate[dir])
                    t[0].maxrate[dir] = str(maxup - realup)
                    #print "index :", t[0].listindex, "; up rate lowered from", maxup, "to", ABCTorrentTemp.listindex          

        else:
            ###########################################################################
            #print "PHASE 2 bis with special algo to favour non URM torrents that want to upload more"
            ###########################################################################
            # This is the algorithm which is used when the Preferences/URM/"Low priority" is ticked.
            # For this algo to kick in, there must be active URM torrents and active non URM torrents that want to raise their up rate.
            # If this is not the case, the algorithm of phase 2 will be run instead.
            # This is meant to give a higher priority to non URM torrents in the distribution of upload bandwidth. If non URM torrents
            # need upload bandwidth, it will be taken from the URM torrents, and if there's not enough there, URM torrents can be stopped
            # to fulfill the demand in bandwidth.
            # -b- Compute the amount of up bandwidth the non URM torrents with up rate > 3kB/s would like to grab
            #     and taking into account the local upload rate settings if they exist.
            # -c- Lower the reserved upload bandwidth of all URM torrents the closer possible to this amount while keeping them above 3kB/s
            #    (Same algo as in phase 2-a-).
            # -d- Raise the reserved upload bandwidth for each non URM torrent of the real global amount that could be taken from the
            #     lowering of the URM torrents.
            # -e- If the non URM torrents would have liked to take more than they were given, queue a URM torrent.

            # -b-
            claimedrate = 0
            for t in nonurmtoberaised:
                ABCTorrentTemp = t[0]
                maxup = float(ABCTorrentTemp.maxrate[dir])
                maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
                if maxlocalup > 0:
#                if ABCTorrentTemp.useLocalRate(dir):
#                    maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
                    newreservedrate = t[1] + self.meancalcupth
                    if newreservedrate > maxlocalup:
                        claimedrate += maxlocalup - maxup
                    else:
                        claimedrate += newreservedrate - maxup
                else:
                    claimedrate += t[1] + self.meancalcupth - maxup
            #print "Claimed up rate :", claimedrate
            
            if claimedrate > 0:
                # -c-
                rate_id = []
                for t in urmtoberaised:
                    maxrate_float = float(ABCTorrentTemp.maxrate[dir])
                    rate_id.append((maxrate_float, t[0]))
                sizerate_id = len(rate_id)
                # Sort by increasing reserved up rate
                rate_id.sort()
                ratetobedistributed = claimedrate
                ratenotassignedforeach = ratetobedistributed / sizerate_id
                # Compute new reserved up rate
                i = 0
                for t in rate_id:
                    newmaxrate = t[0] - ratenotassignedforeach
                    i += 1
                    if newmaxrate < 3:
                        # if some up rate lowering could not be dispatched, it will be distributed to the next torrents
                        # in the list (which are higher in max up rate because the list is sorted this way)
                        newmaxrate = 3
                        if sizerate_id and i != sizerate_id:
                            ratenotassignedforeach += (3 - newmaxrate) / (sizerate_id - i)
                        ratetobedistributed -= t[0] - 3
                    else:
                        ratetobedistributed -= ratenotassignedforeach
                    t[1].maxrate[dir] = str(newmaxrate)
                #print "Up rate not recovered :", ratetobedistributed

                # -d-
                realupfactor = (claimedrate - ratetobedistributed) / claimedrate
                for t in nonurmtoberaised:
                    ABCTorrentTemp = t[0]
                    newreservedrate = t[1] + self.meancalcupth
                    maxup = float(ABCTorrentTemp.maxrate[dir])
                    newmaxup = maxup + (newreservedrate - maxup) * realupfactor
                    maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
                    if maxlocalup > 0:
#                    if ABCTorrentTemp.useLocalRate(dir):
#                        maxlocalup = float(ABCTorrentTemp.maxlocalrate[dir])
                        if newreservedrate > maxlocalup:
                            newmaxup = maxup + (maxlocalup - maxup) * realupfactor
                    ABCTorrentTemp.maxrate[dir] = str(newmaxup)
                    #print "index :", ABCTorrentTemp.listindex, "; up rate raised from", maxup, "to", ABCTorrentTemp.maxrate[dir]

                # -e-
                # 0.05 and not 0 to avoid useless triggering for a too small value or rounding errors
                if ratetobedistributed > 0.05:
                    self.queue.findURMTorrentToStop(resetTimer = True)

        ################################################
        # Set new max upload rate to all active torrents
        ################################################
        self.distributeBandwidth(toberegulated, dir = dir)
    
    def distributeFreeWheeling(self, allactive, dir = "up"):
        #print "FREE WHEELING TORRENTS"
        # If there's still at least 20% of available upload bandwidth, let the torrents do want they want
        # Keep a reserved max upload rate updated not to have to reinitilize it when we'll switch later
        # from free wheeling to controlled status.
        # Give BitTornado the highest possible value for max upload rate to speed up the rate rising
        for t in allactive:
            ABCTorrentTemp = t[0]
            newrate = t[1] + self.meancalcupth
#            if ABCTorrentTemp.useLocalRate(dir):
            maxlocalrate = float(ABCTorrentTemp.getLocalRate(dir))
            if maxlocalrate > 0:
#                maxlocalrate = float(ABCTorrentTemp.maxlocalrate[dir])
                rateToUse = maxlocalrate
                if newrate > maxlocalrate:
                    newrate = maxlocalrate
            else:
                rateToUse = self.MaxRate(dir)
            ABCTorrentTemp.maxrate[dir] = str(newrate)
            # Send to BitTornado
            ABCTorrentTemp.setRate(rateToUse, dir)
        
    def distributePrioritizeLocal(self, localprioactive, dir = "up"):
        # Treat in priority the torrents with a local upload rate setting if "prioritize local" is set
        # As with the free wheeling torrents, keep on tracking the real value of upload rate while giving BitTornado
        # the highest max upload rate to speed up the up rate rising.
        grantedforlocalprioactive = 0
        for t in localprioactive:
            ABCTorrentTemp = t[0]
            newrate = t[1] + self.meancalcupth
            maxlocalrate = float(ABCTorrentTemp.maxlocalrate[dir])
            if newrate > maxlocalrate:
                newrate = maxlocalrate
            grantedforlocalprioactive += newrate - float(ABCTorrentTemp.maxrate[dir])
            ABCTorrentTemp.maxrate[dir] = str(newrate)
            # Send to BitTornado
            ABCTorrentTemp.setRate(maxlocalrate, dir)
        return grantedforlocalprioactive

    # Set the upload rate for all the torrents in the set
    # specify the "rate" parameter to give the torrents a fixed rate
    # rather than using ABCTorrent.maxrate[dir]
    def distributeBandwidth(self, workingset = None, dir = "up"):
        if workingset == None:
            workingset = self.queue.activetorrents
        for ABCTorrentTemp in workingset:
            ABCTorrentTemp.setRate(ABCTorrentTemp.maxrate[dir], dir)

    def MaxRate(self, dir = "up"):
        if dir == "up":
            if self.queue.counters['downloading']:
                # Static overall maximum up rate when downloading
                return float(self.utility.config.Read('maxuploadrate'))        
            else:
                # Static overall maximum up rate when seeding
                return float(self.utility.config.Read('maxseeduploadrate'))
        else:
            return float(self.utility.config.Read('maxdownloadrate'))
           
    # See if any torrents are in the "checking existing data"
    # or "allocating space" stages
    def torrentsChecking(self):
        for ABCTorrentTemp in self.queue.activetorrents:
            if ABCTorrentTemp.isCheckingOrAllocating():
                return True
        return False

    def UploadRateMaximizer(self):
        uploadrate = self.queue.totals['upload']
        
        # Don't do anything if URM isn't enabled
        if self.utility.config.Read('urm') != "1":
            return
        
        # Don't start if any torrents are still in the "checking data" phase:
        if self.torrentsChecking():
            return

        # After ABC starts, the URM waits for urmdelay seconds and then still waits if some torrents are in "checking
        # existing" status to avoid starting too much extra torrents when download/upload has not yet really begun.
        if self.abcstarting:
            if self.urmstartingtime == 0:
                self.urmstartingtime = time()
            if time() - self.urmstartingtime < self.utility.config.Read('urmdelay', "int"):
                return

            self.abcstarting = False
            # Next time this counter will be used for starting torrents
            # We reset it so that it induces no delay on the first time it will used
            self.urmstartingtime = time() - self.utility.config.Read('urmdelay', "int")
            
        # Check if all torrents for normal scheduler have been started
        if self.queue.counters['currentproc'] - self.queue.counters['pause'] < self.utility.config.Read('numsimdownload', "int"):
            self.urm_time['under'] = 0
            self.urm_time['over'] = 0
            return
            
        maxuprate = self.MaxRate()
        
        # Seconds over/under threshold
        thresholdtime = 5

        # Check to see if a new torrent must be started
        lowurmupthreshold = maxuprate - self.utility.config.Read('urmupthreshold', "int")
        if lowurmupthreshold < 0:
            lowurmupthreshold = 0
        if uploadrate < lowurmupthreshold or (uploadrate == 0 and lowurmupthreshold == 0):
            self.urm_time['over'] = 0
            if self.urm_time['under'] == 0:
                self.urm_time['under'] = time()
            # Threshold exceeded for more than urmdelay s ?
            elif time() - self.urm_time['under'] > thresholdtime:
                if self.queue.counters['currentproc'] - self.utility.config.Read('numsimdownload', "int") < self.utility.config.Read('urmmaxtorrent', "int"):
                    self.urm_time['under'] = 0
                    # Search for the torrent to be started
                    urmtorrent = None
                    queuepriority = 6
                    self.moveinlistdetected = False
                    for ABCTorrentTemp in self.queue.proctab:
                        # Criterion to avoid restarting the same torrent more than 2 times in a row
                        # The torrent will be started if :
                        # - Its unique Id is different from the one of the last started torrent
                        # - Or if its Id is the same and the number of times this torrent was started in a row
                        #   is lower than 2.
                        if ABCTorrentTemp == self.laststartedtorrent and self.laststartedtorrentcounter >= 2:
                           continue
                        currentpriority = ABCTorrentTemp.prio
                        # If in manual mode only queue pause are still managed by the scheduler
                        if (ABCTorrentTemp.status['value'] == STATUS_QUEUE
                            and currentpriority < queuepriority):
#                            and currentpriority < queuepriority
#                            and self.utility.config.Read('mode') == '1'):
                            # If stopped torrent are re-enqueued (so not paused), check if at least 400 MB have already been downloaded
                            # to skip this torrent
                            if self.utility.config.Read('fastresume', "boolean") or (ABCTorrentTemp.downsize < 400000000):
                                urmtorrent = ABCTorrentTemp
                                queuepriority = currentpriority
                    # A torrent will be started only if :
                    # no move in the list was detected since the beginning of the scan of the list ;
                    if urmtorrent is not None and not self.moveinlistdetected \
                       and (len(self.queue.availableports) > 0):
                        # Check if the last started torrent was started less than urmdelay seconds ago
                        if time() - self.urmstartingtime < self.utility.config.Read('urmdelay', "int"):
                            return
                        # Save the Id of the torrent about to be started
                        if self.laststartedtorrent == urmtorrent:
                            self.laststartedtorrentcounter += 1
                        else:
                            self.laststartedtorrent = urmtorrent
                            self.laststartedtorrentcounter = 1
                        self.urmstartingtime = time()
                        urmtorrent.maxrate['up'] = "0"
                        
                        urmtorrent.startABCEngine()
                        
                        self.queue.urmtorrents.append(urmtorrent)
                        
                        self.queue.UpdateRunningTorrentCounters()
        # Check to see if a running torrent must be stopped
        # (if the URM has already started some) and put back into the queue
        # If maxuploadrate is unlimited, the URM will never stop a torrent
        elif ((self.utility.config.Read('maxuploadrate', "int") > 0)
               and uploadrate > maxuprate):
            self.urm_time['under'] = 0
            if self.urm_time['over'] == 0:
                # If we're setting urm_time2 equal to time(), then the next check will always return False
                self.urm_time['over'] = time()
            # Threshold exceeded for more than urmdelay s ?
            elif time() - self.urm_time['over'] > thresholdtime:
                self.findURMTorrentToStop()
        else:
            # The upload rate is in the upload rate dead band
            self.urm_time['under'] = 0
            self.urm_time['over'] = 0

    # Stop the URM Torrent with the lowest priority
    def findURMTorrentToStop(self, resetTimer = False):
        if len(self.queue.urmtorrents) == 0:
            # There are no URM torrents
            return

        self.urm_time['over'] = 0
        # Search for the torrent to be stopped (the one with the lower priority and order in the queue)
        # and put it back into the queue
        urmtorrent = None
        urmtorrentpriority = -1
        self.moveinlistdetected = False
        for ABCTorrentTemp in self.queue.urmtorrents:
            currentpriority = ABCTorrentTemp.prio
            if (ABCTorrentTemp.isActive()
                and ABCTorrentTemp.status['value'] != STATUS_PAUSE
                and currentpriority >= urmtorrentpriority):
                urmtorrent = ABCTorrentTemp
                urmtorrentpriority = currentpriority
        # A torrent will be stopped only if no move in the list was detected since the beginning of
        # the scan of the list.
        if urmtorrent is not None and not self.moveinlistdetected:
            self.utility.actionhandler.procQUEUE([urmtorrent])
            try:
                self.queue.urmtorrents.remove(urmtorrent)
            except:
                pass
        
        if resetTimer:
            # Reset the timer to avoid the immediate restarting of a torrent by the URM
            # This stop case is different from a normal stop by the URM with a expected immediate effect : free up bandwidth..
            # Here this torrent is stopped to allow a non URM torrent to raise its upoad rate.
            # So we must wait a little till the non URM torrent starts reacting to this new bandwidth availability.
            self.urmstartingtime = time()

class ABCScheduler(wx.EvtHandler):
    def __init__(self, utility):
        wx.EvtHandler.__init__(self)
        
        self.utility = utility
        self.utility.queue = self
        
        self.utility.actionhandler = ActionHandler(self.utility)
        self.utility.ratemanager = RateManager(self.utility)

        self.proctab = []
        self.activetorrents = []
        self.urmtorrents = []

        self.timer = {}
        
        self.flag = Event()

        # Counters for torrents
        self.counters = { 'currentproc': 0, 
                          'loaded': 0, 
                          'running': 0, 
                          'downloading': 0, 
                          'seeding': 0, 
                          'pause': 0, 
                          'urm': 0 }

        self.totals = { 'upload' : 0.0, 
                        'download' : 0.0, 
                        'connections': 0 }
                   
        # Flag true while the upload rate distribution computing is running
        # This is used to postpone torrent deleting in the list while this thread is running
        self.urmdistribrunning = False

        # Flag to check if torrents were moved in the list while the URM is running
        # If set to true, the result of the URM will be trashed, because it can be
        # wrong in relation with the new position of the torrents in the list. The
        # next run of the URM may give a better result.
        # This is not used in the scheduler because it doesn't run cyclically.
        self.moveinlistdetected = False

        minport = self.utility.config.Read('minport', "int")
        maxport = self.utility.config.Read('maxport', "int")

        self.availableports = range(minport, maxport + 1)
        if self.utility.config.Read('randomport') == '1':
            # Randomly shuffle the range of ports
            shuffle(self.availableports)

        self.UpdateRunningTorrentCounters()

        EVT_INVOKE(self, self.onInvoke)
      
    # Update the counters for torrents in a single unified place
    def CalculateTorrentCounters(self):
        self.counters = { 'currentproc': 0, 
                          'loaded': 0, 
                          'running': 0, 
                          'downloading': 0, 
                          'seeding': 0, 
                          'pause': 0, 
                          'urm': 0 }
               
        for ABCTorrentTemp in self.activetorrents:
            # Torrent is active
            if ABCTorrentTemp.status['value'] == STATUS_PAUSE:
                self.counters['pause'] += 1
            elif ABCTorrentTemp.status['completed']:
                self.counters['seeding'] += 1
            else:
                self.counters['downloading'] += 1

        self.counters['loaded'] += len(self.proctab)                    
        self.counters['running'] = len(self.activetorrents)
        self.counters['urm'] = len(self.urmtorrents)
        
        if self.utility.config.Read('trigwhenfinishseed') == "1":
            self.counters['currentproc'] = self.counters['running']
        else:
            self.counters['currentproc'] = self.counters['running'] - self.counters['seeding']
        
    def UpdateRunningTorrentCounters(self):
        self.CalculateTorrentCounters()
            
        statusfunc = self.utility.frame.abc_sb.SetStatusText      
        statusfunc((" " + self.utility.lang.get('abbrev_loaded') + " %u " % self.counters['loaded']), 1)
        statusfunc((" " + self.utility.lang.get('abbrev_running') + " %u " % self.counters['running']), 2)
        statusfunc((" " + self.utility.lang.get('abbrev_downloading') + " %u " % self.counters['downloading']), 3)
        statusfunc((" " + self.utility.lang.get('abbrev_seeding') + " %u " % self.counters['seeding']), 4)
        statusfunc((" " + self.utility.lang.get('abbrev_pause') + " %u " % self.counters['pause']), 5)
        
        try:
            if hasattr(self.utility, "bottomline2"):
                self.utility.bottomline2.queuecurrent.SetLabel(str(self.counters['currentproc'] - self.counters['urm']))
                self.utility.bottomline2.urmcurrent.SetLabel(str(self.counters['urm']))
        except wx.PyDeadObjectError:
            pass

    def getDownUpConnections(self):
        # Ask UD/DL speed of all threads
        ########################################
        totalupload     = 0.0
        totaldownload   = 0.0
        totalconnections = 0

        for ABCTorrentTemp in self.activetorrents:
            if ABCTorrentTemp.status['value'] != STATUS_PAUSE:
                totaldownload += ABCTorrentTemp.getColumnValue(10)
                totalupload += ABCTorrentTemp.getColumnValue(11)
                totalconnections += ABCTorrentTemp.getColumnValue(24)
                
        self.totals['upload'] = totalupload
        self.totals['download'] = totaldownload
        self.totals['connections'] = totalconnections
        
    def updateTrayAndStatusBar(self):
        maxuprate = self.utility.ratemanager.MaxRate("up")
        if maxuprate == 0:
            upspeed = self.utility.speed_format(self.totals['upload'], truncate = 1)
            upratecap = "oo"
        else:
            upspeed = self.utility.size_format(self.totals['upload'], truncate = 1, stopearly = "KB", applylabel = False)
            upratecap = self.utility.speed_format((maxuprate * 1024), truncate = 0, stopearly = "KB")
        uploadspeed = upspeed + " / " + upratecap

        maxdownrate = self.utility.ratemanager.MaxRate("down")
        if maxdownrate == 0:
            downspeed = self.utility.speed_format(self.totals['download'], truncate = 1)
            downratecap = "oo"
        else:
            downspeed = self.utility.size_format(self.totals['download'], truncate = 1, stopearly = "KB", applylabel = False)
            downratecap = self.utility.speed_format((maxdownrate * 1024), truncate = 0, stopearly = "KB")
        downloadspeed = downspeed + " / " + downratecap
        
        try:
            # update value in minimize icon
            ###########################################
            if self.utility.frame.tbicon is not None and self.utility.frame.tbicon.IsIconInstalled():
                icontext = "ABC" + "\n\n" + \
                           self.utility.lang.get('totaldlspeed') + " " + downloadspeed + "\n" + \
                           self.utility.lang.get('totalulspeed') + " " + uploadspeed + " "
                self.utility.frame.tbicon.SetIcon(self.utility.icon, icontext)

            # update in status bar
            ##########################################
            if self.utility.frame.abc_sb is not None:
                self.utility.frame.abc_sb.SetStatusText(" " + self.utility.lang.get('abbrev_connections') + " " + str(int(self.totals['connections'])), 6)
                self.utility.frame.abc_sb.SetStatusText(" " + self.utility.lang.get('abbrev_down') + " " + downloadspeed, 7)
                self.utility.frame.abc_sb.SetStatusText(" " + self.utility.lang.get('abbrev_up') + " " + uploadspeed, 8)
        except wx.PyDeadObjectError:
            pass
                                
    def CyclicalTasks(self):
        self.getDownUpConnections()
            
        try:
            self.updateTrayAndStatusBar()

            self.utility.ratemanager.RunTasks()
       
            try:
                # Run postponed deleting events
                while self.utility.window.postponedevents:
                    ev = self.utility.window.postponedevents.pop(0)
                    #print "POSTPONED EVENT : ", ev[0]
                    ev[0](ev[1])
                self.utility.list.Enable()
            except wx.PyDeadObjectError:
                pass

            # Try invoking the scheduler
            # (just in case we need to start more stuff:
            #  should return almost immediately otherwise)
            self.Scheduler()

            # Start Timer
            ##########################################
            self.timer['frequent'] = Timer(2, self.CyclicalTasks)
            self.timer['frequent'].start()
        except:
            pass
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())   # report exception here too
            
    def InfrequentCyclicalTasks(self, update = True):
        if update:
            # Send a "keep alive" message to interconn
            # (and to the webservice if it's running)
            if not self.utility.abcquitting:
                ClientPassParam("KEEPALIVE")
                self.utility.webserver.client.sendCmd("KEEPALIVE")
            
            try:
                if self.timer['infrequent'] is not None:
                    self.timer['infrequent'].cancel()
            except:
                pass
#                data = StringIO()
#                print_exc(file = data)
#                sys.stderr.write(data.getvalue())
        
            self.updateTorrentList()

        self.timer['infrequent'] = Timer(300, self.InfrequentCyclicalTasks)
        self.timer['infrequent'].start()

               
    def onInvoke(self, event):
        if not self.flag.isSet():
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.flag.isSet():
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))
              
    def updateAndInvoke(self, updateCounters = True, updateList = True, invokeLater = True, fullListUpdate = False):
        if updateCounters:
            # Update counter for running torrents
            self.UpdateRunningTorrentCounters()
        if updateList:
            self.updateTorrentList(fullListUpdate)
        # Only invoke the scheduler if we're not shutting down
        if invokeLater:
            self.invokeLater(self.Scheduler)

    #from 3 sources, add from file, add from URL, autoadd
    def addNewProc(self, src, dest = None, forceasklocation = False, dotTorrentDuplicate = False, dontremove = False, caller = "", doupdate = True):
        #from file, URL maybe down torrent.lst from addProc
        # change at onChooseFile make sure they choose dest
        # dotTorrentDuplicate : To avoid asking the user twice about duplicate (for torrent file name and torrent name)
        #                       True if .torrent is duplicate ; not used if caller==web"

        # Did we succeed in adding the torrent?
        error = None
        ABCTorrentTemp = None
        
        # Check to see the the src file actually exists:
        if not os.access(src, os.R_OK):
            if caller != "web":
                dlg = wx.MessageDialog(None, src + '\n' +
                                                    self.utility.lang.get('failedtorrentmissing'), self.utility.lang.get('error'), wx.OK|wx.ICON_ERROR)
                result = dlg.ShowModal()
                dlg.Destroy()
                dontremove = True
            error = ".torrent file doesn't exist or can't be read"
        else:
            ABCTorrentTemp = ABCTorrent(self, src, dest = dest, forceasklocation = forceasklocation, caller = caller)       
            
            if ABCTorrentTemp.metainfo is None:
                if caller != "web":
                    dlg = wx.MessageDialog(None, src + '\n' +
                                                        self.utility.lang.get('failedinvalidtorrent') + '\n' +
                                                        self.utility.lang.get('removetorrent'), self.utility.lang.get('error'), wx.YES_NO|wx.ICON_ERROR)
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if (result == wx.ID_NO):
                        dontremove = True
                error = "Invalid torrent file"
                    
            # If the torrent doesn't have anywhere to save to, return with an error
            elif ABCTorrentTemp.dest is None:
                error = "No destination to save to"
    
            # Search for duplicate torrent name (inside .torrent file) and hash info
            # only if the .torrent is not already a duplicate
            elif not dotTorrentDuplicate:
                torrent = self.getABCTorrent(info_hash = ABCTorrentTemp.infohash)
                if (torrent is not None
                    and torrent.filename == ABCTorrentTemp.filename):
                    result = None
                    if caller != "web":
                        message = src + '\n' + self.utility.lang.get('duplicatetorrentmsg')
                        dlg = wx.MessageDialog(None,
                                               message,
                                               self.utility.lang.get('duplicatetorrent'),
                                               wx.YES_NO|wx.ICON_EXCLAMATION)
                        result = dlg.ShowModal()
                        dlg.Destroy()
                    if (caller == "web") or (result == wx.ID_NO):
                        error = "Duplicate torrent name"

        # We encountered an error somewhere in the process
        if error is not None:
            # Don't remove if the torrent file is already being used by an existing process
            # Removing will cause problems with the other process
            if not dontremove:
                try:
                    os.remove(src)
                except:
                    pass
            ABCTorrentTemp = None
            return False, error, ABCTorrentTemp
       
        if doupdate and ABCTorrentTemp is not None:
            self.proctab.append(ABCTorrentTemp)
            ABCTorrentTemp.postInitTasks()
            self.updateAndInvoke()
        
        return True, self.utility.lang.get('ok'), ABCTorrentTemp
        
    def addOldProc(self, indexval):
        torrentconfig = self.utility.torrentconfig
        
        index = str(indexval)
        
        try:
            if not torrentconfig.has_section(index):
                return False
        except:
            return False
        
        # Torrent information
        filename = torrentconfig.Read("src", section = index)
        # Format from earlier 2.7.0 test builds:
        if filename == "":
            # If the src is missing, then we should not try to add the torrent
            sys.stdout.write("Filename is empty for index: " + str(index) + "!\n")
            return False
        elif filename.startswith(self.utility.getPath()):
            src = filename
        else:
            src = os.path.join(self.utility.getPath(), "torrent", filename)
        dest = torrentconfig.Read("dest", section = index)
        
        success, error, ABCTorrentTemp = self.addNewProc(src, dest = dest, doupdate = False)
        
        if not success:
            # Didn't get a valid ABCTorrent object
            return False
        
        self.proctab.append(ABCTorrentTemp)
        ABCTorrentTemp.postInitTasks()
        
        return True
             
    def readTorrentList(self):
        # Convert list in older format if necessary
        convertOldList(self.utility)
        
        numbackups = 3
        
        # Manage backups
        filenames = [ os.path.join(self.utility.abcpath, "torrent.list") ]
        for i in range(1, numbackups + 1):
            filenames.append(filenames[0] + ".backup" + str(i))
            
        for i in range (numbackups, 0, -1):
            if os.access(filenames[i-1], os.R_OK):
                copy2(filenames[i-1], filenames[i])
        
        index = 0
        while self.addOldProc(index):
            index += 1
            
        self.updateAndInvoke(updateList = False)
      
    def updateTorrentList(self, flushOnly = True):
        torrentconfig = self.utility.torrentconfig
       
        if not flushOnly:
            for ABCTorrentTemp in self.proctab:
                ABCTorrentTemp.torrentconfig.writeAll()
                        
        self.eraseBeyondList()
        
        try:
            torrentconfig.DeleteGroup("dummygroup")
        except:
            pass

        torrentconfig.Flush()
    
    def eraseBeyondList(self):
        index = len(self.proctab)
        torrentconfig = self.utility.torrentconfig
        
        while torrentconfig.has_section(str(index)):
            try:
                torrentconfig.DeleteGroup(str(index))
            except wx.PyAssertionError:
                # Workaround for bug in wxPython 2.5.2.x
                # this will throw an PyAssertionError when
                # trying to delete a group if it is the only one left
                break
            index += 1
        
    def Scheduler(self):
        if self.flag.isSet():
            return
        self.flag.set()
        
        numsimdownload = self.utility.config.Read('numsimdownload', "int")
            
        # Choose job by highest priority
        #################################
        while (self.counters['currentproc'] < numsimdownload
               and (len(self.availableports) > 0)
               and (not self.utility.abcquitting)):
            torrent = None
            queuepriority = 6
            change = False
            # "Convert" a urm torrent
            if len(self.urmtorrents) > 0:
                for ABCTorrentTemp in self.urmtorrents:
                    currentpriority = ABCTorrentTemp.prio
                    if (currentpriority < queuepriority):
                        torrent = ABCTorrentTemp
                        queuepriority = currentpriority
                if (torrent is not None):
                    try:
                        self.urmtorrents.remove(ABCTorrentTemp)
                        change = True
                    except:
                        pass
            elif len(self.activetorrents) < len(self.proctab):
                for ABCTorrentTemp in self.proctab:
                    currentpriority = ABCTorrentTemp.prio
                    if (ABCTorrentTemp.status['value'] == STATUS_QUEUE
                        and currentpriority < queuepriority):
                        torrent = ABCTorrentTemp
                        queuepriority = currentpriority
                if (torrent is not None):
                    change = torrent.actions.resume()
                else:
                    break
            else:
                break

            if change:
                self.UpdateRunningTorrentCounters()
        
        self.flag.clear()
      
    def changeABCParams(self):
        self.utility.bottomline2.changeNumSim()
        self.utility.bottomline2.changeURM()
        
        for ABCTorrentTemp in self.proctab:
            #Local doesn't need to affect with change ABC Params
            ABCTorrentTemp.resetUploadParams()

        # Queue all the urmtorrents if URM has been disabled:
        if self.utility.config.Read('urm') == "0":
            self.utility.actionhandler.procQUEUE(self.urmtorrents)

        self.updateAndInvoke()

    # Move a line of the list from index1 to index2
    def MoveItems(self, listtomove, direction = 1):
        self.moveinlistdetected = True

        listtomove.sort()
        
        if direction == 1:
            # Moving items down, need to reverse the list
            listtomove.reverse()
            # Start offset will be one greater than the
            # first item in the resulting set
            startoffset = -1
            endoffset = 0
        # We're only going to allow moving up or down
        else:
            direction = -1
            # End offset will be one greater than the
            # last item in the set
            startoffset = 0
            endoffset = 1
        newloc = []

        for index in listtomove:
            if (direction == 1) and (index == len(self.proctab) - 1):
                #Last Item can't move down anymore
                newloc.append(index)
            elif (direction == -1) and (index == 0):
                # First Item can't move up anymore
                newloc.append(index)
            elif newloc.count(index + direction) != 0 :
                #Don't move if we've already moved the next item
                newloc.append(index)
            else:
                ABCTorrentTemp = self.proctab.pop(index)
                self.proctab.insert(index + direction, ABCTorrentTemp)
                newloc.append(index + direction)

        # Only need update if something has changed
        if len(newloc) > 0:
            newloc.sort()
            start = newloc[0] + startoffset
            end = newloc[-1] + endoffset
            self.updateListIndex(startindex = start, endindex = end)
            self.updateAndInvoke(updateCounters = False)       
            
        return newloc

    def MoveItemsTop(self, selected):
        self.moveinlistdetected = True

        for index in selected:
            if index != 0:       # First Item can't move up anymore
                ABCTorrentTemp = self.proctab.pop(index)
                self.proctab.insert(0, ABCTorrentTemp)               

        if len(selected) > 0:
            self.updateListIndex(startindex = 0, endindex = selected[0])
            self.updateAndInvoke(updateCounters = False)
        
        return True
        
    def MoveItemsBottom(self, selected):
        self.moveinlistdetected = True

        for index in selected:
            if index < len(self.proctab) - 1:
                ABCTorrentTemp = self.proctab.pop(index)
                self.proctab.append(ABCTorrentTemp)
                
        if len(selected) > 0:
            self.updateListIndex(startindex = selected[0])
            self.updateAndInvoke(updateCounters = False)
        
        return True

    def clearAllCompleted(self):
        removelist = []
        for ABCTorrentTemp in self.proctab:
            if ABCTorrentTemp.isDoneUploading():
                removelist.append(ABCTorrentTemp)
        if self.utility.config.Read('movecompleted', "boolean"):
            self.utility.actionhandler.procMOVE(removelist)
        self.utility.actionhandler.procREMOVE(removelist)
                
    # used only when doing an update after applying changes in ABC_Tweak
    def updateInactiveCol(self):
        for ABCTorrentTemp in self.proctab:
            ABCTorrentTemp.updateColumns()
            
    def clearScheduler(self):       
        try:
            if self.timer['frequent'] is not None:
                self.timer['frequent'].cancel()
                del self.timer['frequent']
        except:
            pass

        for ABCTorrentTemp in self.proctab:
            ABCTorrentTemp.shutdown()
            self.utility.closedlg.update()
        
        # Update the torrent list
        self.updateAndInvoke(updateCounters = False)

        # Stop the timer for updating the torrent list
        try:
            if self.timer['infrequent'] is not None:
                self.timer['infrequent'].cancel()
                del self.timer['infrequent']
        except:
            pass
            
    def getABCTorrent(self, index = -1, info_hash = None):
        # Find it by the index
        if index >= 0 and index < len(self.proctab):
            return self.proctab[index]
        # Can't find it by index and the hash is none
        # We're out of luck
        elif info_hash is None:
            return None

        # Look for the hash value
        for ABCTorrentTemp in self.proctab:
            if ABCTorrentTemp.infohash == info_hash:
                return ABCTorrentTemp

    def sortList(self, colid = 4, reverse = False):
        # Sort by uprate first
        self.proctab.sort(key = lambda x: x.getColumnValue(colid), reverse = reverse)
        self.updateListIndex()
        self.updateAndInvoke(updateCounters = False, invokeLater = False)

    def updateListIndex(self, startindex = 0, endindex = None):
        # Can't update indexes for things that aren't in the list anymore
        if startindex >= len(self.proctab):
            return

        if startindex < 0:
            startindex = 0
        if endindex is None or endindex >= len(self.proctab):
            endindex = len(self.proctab) - 1

        for i in range(startindex, endindex + 1):
            ABCTorrentTemp = self.proctab[i]
            ABCTorrentTemp.listindex = i
            ABCTorrentTemp.updateColumns()
            ABCTorrentTemp.updateColor(force = True)
            ABCTorrentTemp.torrentconfig.writeAll()
        