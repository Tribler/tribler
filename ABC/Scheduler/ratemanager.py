import sys
import wx
import os

from threading import Event
from time import time, clock

#from traceback import print_exc
#from cStringIO import StringIO

from Utility.constants import * #IGNORE:W0611
from Utility.helpers import union, difference


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


################################################################
#
# Class: RateManger
#
# Keep the upload and download rates for torrents within
# the defined local and global limits
#
################################################################
class RateManager(wx.EvtHandler):
    def __init__(self, queue):
        wx.EvtHandler.__init__(self)
               
        self.queue = queue
        self.utility = queue.utility

        # For Upload Rate Maximizer
        # Time when the upload rate is lower than the URM threshold for the first time
        self.urm_time = { 'under' : 0.0, 
                          'checking'  : 0.0 }
                
        # bandwidth between reserved rate and measured rate
        # above which a torrent will have its reserved rate lowered
        self.calcupth1 = 2.3
        
        # bandwidth between reserved rate and measured rate
        # under which a torrent will have its reserved rate raised
        self.calcupth2 = 0.7
        
        self.meancalcupth = (self.calcupth1 + self.calcupth2) / 2
        
        self.lastmaxrate = -1

        # Minimum rate setting
        # 3 KB/s for uploads, 0.01KB/s for downloads
        # (effectively, no real limit for downloads)
        self.rateminimum = { "up": 3.0,
                             "down": 0.01 }

        self.flag = Event()
        EVT_INVOKE(self, self.onInvoke)

    def onInvoke(self, event):
        if not self.flag.isSet():
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = None, kwargs = None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        if not self.flag.isSet():
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))
                
    def RunTasks(self):
        self.invokeLater(self.RateTasks)
            
    def RateTasks(self):
        self.flag.set()
        
        self.UploadRateMaximizer()
        
        self.CalculateBandwidth("down")
        self.CalculateBandwidth("up")
        
        self.flag.clear()

    def MaxRate(self, dir = "up"):
        Read = self.utility.config.Read
        
        if dir == "up":
            if self.utility.torrents["downloading"]:
                # Static overall maximum up rate when downloading
                return Read('maxuploadrate', "float")
            else:
                # Static overall maximum up rate when seeding
                return Read('maxseeduploadrate', "float")
        else:
            return Read('maxdownloadrate', "float")
           
    # See if any torrents are in the "checking existing data"
    # or "allocating space" stages
    def torrentsChecking(self):
        for torrent in self.utility.torrents["active"].keys():
            if torrent.status.isCheckingOrAllocating():
                return True
        return False

    def UploadRateMaximizer(self):
        Read = self.utility.config.Read
               
        # Don't do anything if URM isn't enabled
        if not Read('urm', "boolean"):
            return
        
        # Don't start:
        # - if no torrents are inactive
        # - if any torrents are still in the "checking data" phase
        # - if not enough time has passed after torrents finished checking
        if not self.utility.torrents["inactive"]:
            self.urm_time['under'] = 0
            return
        
        if not self.urm_time['checking'] or self.torrentsChecking():
            self.urm_time['checking'] = time()
            return
            
        # See how long to wait between checking torrents
        delay = Read('urmdelay', "int")
            
        # If a torrent was checking, allow it some time to start up
        # (wait a minimum of 45 seconds for a torrent to start up,
        #  longer if the delay between starting torrents is longer)
        if time() - self.urm_time['checking'] < max(delay, 45):
            return

        # Find the "low" value for upload rate that we're checking for
        lowupthreshold = self.MaxRate("up") - Read('urmupthreshold', "int")
        if lowupthreshold < 0:
            lowupthreshold = 0
        
        uploadrate = self.queue.totals_kb['up']
        
        # Upload rate is below the threshold
        if uploadrate < lowupthreshold or (uploadrate == 0.0 and lowupthreshold == 0.0):
            if self.urm_time['under'] == 0:
                self.urm_time['under'] = time()
            
            # Threshold exceeded for more than urmdelay s ?
            elif time() - self.urm_time['under'] > Read('urmdelay', "int"):
                # Get the next torrent to start
                inactivetorrents = self.utility.queue.getInactiveTorrents(1)
                if not inactivetorrents:
                    return
                
                self.urm_time['under'] = 0
                
                self.utility.actionhandler.procRESUME(inactivetorrents)
                
                self.queue.UpdateRunningTorrentCounters()
        
        # The upload rate is good for now
        else:
            self.urm_time['under'] = 0

##########################################################################################
            
    def CalculateBandwidth(self, dir = "up"):
        if dir == "up":
            workingset = union(self.utility.torrents["downloading"], self.utility.torrents["seeding"])
        else:
            workingset = self.utility.torrents["downloading"]

        # Limit working set to active torrents with connections:
        workingset = [torrent for torrent in workingset if torrent.status.isActive() and torrent.connection.engine.hasConnections]

        # No active file, not need to calculate
        if not workingset:
            return
        
        maxrate = self.MaxRate(dir)
        # See if global rate settings are set to unlimited
        if maxrate == 0:
            # Unlimited rate
            for torrent in workingset:
                torrent.connection.maxrate[dir] = torrent.connection.getLocalRate(dir)
                torrent.connection.setRate(torrent.connection.maxrate[dir], dir)
            return
        
        #print "====================== BEGINNING ALGO ======= th1=%.1f ; th2=%.1f =============================" % (self.calcupth1, self.calcupth2)

        #######################################################
        # - Find number of completed/incomplete torrent
        # - Number of torrent using local setting
        # - bandwidth already used by torrents
        # - Sorting of torrents in lists according to their will in matter of upload rate :
        #   (tobelowered, toberaisedinpriority, toberaised, nottobechanged)
        #######################################################

        # Option set in Preferences/Queue.
        # If not set, torrents with rate local settings are treated like other torrents, except they have their
        # own max rate they can't cross over. The consequence is a behaviour slightly different from the behavior of
        # ABC releases prior to 2.7.0.
        # If set, this gives the algorithm the behaviour of ABC releases prior to 2.7.0 : the torrents with an rate
        # local setting will be granted bandwidth in priority to fulfill their local setting, even is this one
        # is higher than the global max rate setting, and even if this bandwidth must be taken from other active
        # torrents wihout a local rate setting. These torrents will not take part in the rate exchange
        # between active torrents when all bandwidth has been distributed, since they will have been served in priority.
        prioritizelocal = self.utility.config.Read('prioritizelocal', "boolean")

        # torrents with local rate settings when prioritizelocal is set (see prioritizelocal)
        localprioactive = []       
    
        # torrents for which measured rate is lowering and so reserved rate can be lowered
        tobelowered = []
     
        # torrents for which measured rate is growing and so reserved rate can be raised,
        # (with reserved rate > 3 kB/s for uploading)
        toberaised  = []                           

        # torrents for which reserved rate can be raised, with reserved rate < 3 kB/s
        # These will always be raised even there's no available up bandwith, to fulfill the min 3 kB/s rate rule
        toberaisedinpriority = []                             

        # torrents for which reserved rate is not to be changed and is > rateminimum; (for these, the
        # measured rate is between (max upload reserved - calcupth1) and (max upload reserved - calcupth2)
        nottobechanged = []   

        meanrate = 0.0            # mean max rate for torrents to be raised or not to be changed ; it will be used to decide which torrents
                              # must be raised amongst those that want to get higher and that must share the available up bandwidth. The torrents
                              # that don't want to change their rate and that are below 3 kB/s are not taken into account on purpose, because
                              # these ones will never be lowered to give more rate to a torrent that wants to raise its rate, or to
                              # compensate for the rate given to torrents to be raised in priority.

        for torrent in workingset:
            # Active Torrent
            currentrate = torrent.connection.rate[dir]

            maxrate_float = torrent.connection.maxrate[dir]

            # Torrents dispatch
            if prioritizelocal and torrent.connection.getLocalRate(dir, True):
                localprioactive.append(torrent)
            elif currentrate < 0.05:
                # These are the torrents that don't want to have their rate changed and that have an allmost null rate
                # They will not go lower, we can reset their reserved rate until they want to get higher
                torrent.connection.maxrate[dir] = 0.0
            elif maxrate_float - currentrate > self.calcupth1:
                tobelowered.append(torrent)
            elif maxrate_float - currentrate <= self.calcupth2:
                if currentrate < self.rateminimum[dir]:
                    toberaisedinpriority.append(torrent)
                else:
                    toberaised.append(torrent)
                    meanrate += maxrate_float
            elif currentrate > self.rateminimum[dir]:
                nottobechanged.append(torrent)
                meanrate += maxrate_float

#        print "index: %i ; rate: %.1f ; reserved: %.1f ; maxlocal: %.1f" % (torrent.listindex, \
#              currentrate, maxrate_float, float(torrent.connection.maxlocalrate[dir]))

        ###############################################
        # Calculate rate for each torrent
        ###############################################
        
        availableratetobedistributed = maxrate
        
        if ((availableratetobedistributed != 0)
            and (1 - (self.queue.totals_kb[dir] / availableratetobedistributed) > 0.20)):
            #print "FREE WHEELING TORRENTS"
            # If there's still at least 20% of available bandwidth, let the torrents do want they want
            # Keep a reserved max rate updated not to have to reinitilize it when we'll switch later
            # from free wheeling to controlled status.
            # Give BitTornado the highest possible value for max rate to speed up the rate rising
            for torrent in workingset:
                newrate = torrent.connection.rate[dir] + self.meancalcupth
                maxlocalrate = float(torrent.connection.getLocalRate(dir))
                if maxlocalrate > 0:
                    rateToUse = maxlocalrate
                    if newrate > maxlocalrate:
                        newrate = maxlocalrate
                else:
                    rateToUse = self.MaxRate(dir)
                torrent.connection.maxrate[dir] = newrate
                # Send to BitTornado
                torrent.connection.setRate(rateToUse, dir)
            return

        ###########################################################################
        # First treat special torrents before going on sharing and distributing
        ###########################################################################

        # Treat in priority the torrents with rate below 3 kB/s and that want to get a higher rate
        grantedfortoberaisedinpriority = 0.0
        for torrent in toberaisedinpriority:
            newreservedrate = torrent.connection.rate[dir] + self.meancalcupth
            if newreservedrate > self.rateminimum[dir]:
                grantedfortoberaisedinpriority += self.rateminimum[dir] - torrent.connection.maxrate[dir]
                torrent.connection.maxrate[dir] = self.rateminimum[dir]
            else:
                grantedfortoberaisedinpriority += newreservedrate - torrent.connection.maxrate[dir]
                torrent.connection.maxrate[dir] = newreservedrate

        # Treat in priority the torrents with a local rate setting if "prioritize local" is set
        # As with the free wheeling torrents, keep on tracking the real value of rate while giving BitTornado
        # the highest max rate to speed up the rate rising.
        grantedforlocaltoberaised = 0.0
        for torrent in localprioactive:
            newrate = torrent.connection.rate[dir] + self.meancalcupth
            maxlocalrate = float(torrent.connection.getLocalRate(dir))
            if newrate > maxlocalrate:
                newrate = maxlocalrate
            grantedforlocaltoberaised += newrate - torrent.connection.maxrate[dir]
            torrent.connection.maxrate[dir] = newrate
            # Send to BitTornado
            torrent.connection.setRate(maxlocalrate, dir)

        # Torrents that want to be lowered in rate (and give back some reserved bandwidth)
        givenbackbytobelowered = 0.0
        for torrent in tobelowered:
            newreservedrate = torrent.connection.rate[dir] + self.meancalcupth
            givenbackbytobelowered += newreservedrate - torrent.connection.maxrate[dir]
            torrent.connection.maxrate[dir] = newreservedrate
        
        # Add to available rate to be distributed the rate given back by the torrents that have been lowered ;
        # Substract from available rate the rate used for each torrent that have been be raised in priority (torrents with rate
        # below 3 kB/s and that want to get higher).
        availableratetobedistributed += givenbackbytobelowered - grantedfortoberaisedinpriority - grantedforlocaltoberaised - self.queue.totals_kb[dir]
        #print "availableratetobedistributed is %.3f" % availableratetobedistributed

        # localprioactive torrents have already been updated if prioritizelocal is set
        toberegulated = [torrent for torrent in workingset if torrent not in localprioactive]

        # There's nothing to do if no torrent want to be raised
        if not toberaised:
            ################################################
            # Set new max rate to all active torrents
            ################################################
            for torrent in toberegulated:
                torrent.connection.setRate(torrent.connection.maxrate[dir], dir)
            return
               
        if availableratetobedistributed > 0:
            ###########################################################################
            #print "PHASE 1"
            ###########################################################################
            # Phase 1 : As long as there's available bandwidth below the total max to be distributed, I give some
            # to any torrents that asks for it.
            # There's a special case with torrents to be raised that have a local max rate : they must be topped to their max local
            # rate and the surplus part of the reserved bandwidth may be reused.
            # To sum up : In Phase 1, the measured rate is leading the reserved rate.

            # Check if all torrents that claim a higher reserved rate will be satisfied
            claimedrate = 0.0
            for torrent in toberaised:
                maxup = torrent.connection.maxrate[dir]
                newreservedrate = torrent.connection.rate[dir] + self.meancalcupth
                toadd = newreservedrate

                maxlocalup = float(torrent.connection.getLocalRate(dir))
                if maxlocalup > 0 and newreservedrate > maxlocalup:
                    toadd = maxlocalup
                
                claimedrate += toadd - maxup

            #print "Claimed rate :", claimedrate
            #print "Available rate :", availableratetobedistributed

            if claimedrate <= availableratetobedistributed:
                realupfactor = 1
            else:
                realupfactor = availableratetobedistributed / claimedrate

            # If all claims can be fulfilled ; we distribute and go to end.
            # If there's not enough remaining rate to fulfill all claims, the remaining available rate will be
            # distributed proportionally between all torrents that want to raise.
            for torrent in toberaised:
                maxup = torrent.connection.maxrate[dir]
                newreservedrate = torrent.connection.rate[dir] + self.meancalcupth
                newmaxup = maxup + (newreservedrate - maxup) * realupfactor

                maxlocalup = float(torrent.connection.getLocalRate(dir))
                if maxlocalup > 0 and newreservedrate > maxlocalup:
                    newmaxup = maxup + (maxlocalup - maxup) * realupfactor

                torrent.connection.maxrate[dir] = newmaxup
                #print "index :", torrent.listindex, "; rate raised from", maxup, "to", torrent.connection.maxrate[dir]
            
            ################################################
            # Set new max rate to all active torrents
            ################################################
            for torrent in toberegulated:
                torrent.connection.setRate(torrent.connection.maxrate[dir], dir)
            return

        ###########################################################################
        #print "PHASE 2"
        ###########################################################################
        # -a- Each torrent that wants its rate to be raised or not to be changed will have its reserved rate lowered
        #     to compensate the bandwidth given in priority to torrents with rate below 3 kB/s and torrents with local rate
        #     settings if "prioritize local" is set. This lowering must not bring the reserved rate of a torrent below 3 kB/s.
        #     Torrents will be sorted by their reserved rate and treated from the lower to the bigger. If a part of the lowering
        #     cannot be achieved with a torrent,it will be dispatched to the pool of the remaining torrents to be treated.
        #     After this, there may still be more total rate reserved than available rate because of the min 3 kB/s rule.
        ###########################################################################

        # -a-
        if availableratetobedistributed < 0:
            rate_id = []
            pooltobelowered = toberaised + nottobechanged
            
            rate_id = [torrent for torrent in pooltobelowered if torrent.connection.rate[dir] > self.rateminimum[dir]]

            sizerate_id = len(rate_id)
            # Sort by increasing reserved rate
            rate_id.sort(key = lambda x: x.connection.maxrate[dir])
            if rate_id:
                ratenotassignedforeach = availableratetobedistributed / sizerate_id
            # Compute new reserved rate
            i = 0
            for torrent in rate_id:
                # (availableratetobedistributed and ratenotassignedforeach are negative numbers)
                newmaxrate = torrent.connection.maxrate[dir] + ratenotassignedforeach
                i += 1
                if newmaxrate < self.rateminimum[dir]:
                    # if some rate lowering could not be dispatched, it will be distributed to the next torrents
                    # in the list (which are higher in max rate because the list is sorted this way)
                    if i != sizerate_id:
                        ratenotassignedforeach += (newmaxrate - self.rateminimum[dir]) / (sizerate_id - i)
                    newmaxrate = self.rateminimum[dir]
                torrent.connection.maxrate[dir] = newmaxrate
            #    print "%i lowered from %.3f to %.3f" % (t[1].listindex, t[0], newmaxrate)
            #print "availableratetobedistributed is now %.3f" % availableratetobedistributed

        ###########################################################################
        #print "PHASE 2 algo with mean rate"
        ###########################################################################
        # Phase 2 : There's no more available bandwidth to be distributed, I split the total max between active torrents.
        # -b- Compute the mean max rate for the pool of torrents that want their rate to be raised or not to be changed
        #     and list torrents below and above that mean value.
        # -c- The regulation for torrents that want to have their rate raised is computed this way :
        #     The idea is to target a mean rate for all torrents that want to raise their rate or don't want to have it
        #     changed, taking into account the max rates of local settings, and the fact that no torrent must be lowered down below
        #     3 kB/s.
        # To sum up : In Phase 2, the reserved rate is leading the real rate .

        # -b-
        # Mean reserved rate calculation
        # If prioritizelocal is set, all torrents with a local rate settting are completely excluded from
        # the bandwidth exchange phase between other torrents. This is because this phase
        # targets a mean rate between torrents that want to upload more, and when prioritizelocal
        # is set, torrents with a local rate settting can be very far from this mean rate and their
        # own purpose is not to integrate the pool of other torrents but to live their own life (!)

        if toberaised or nottobechanged:
            meanrate /= len(toberaised) + len(nottobechanged)
        #print "Mean rate over 3 kB/s : %.1f" % meanrate

        raisedbelowm = []         # ids for torrents to be raised and with reserved rate below mean max rate
        allabovem = []            # ids for torrents to be raised or not to be changed and with reserved rate above mean max rate
        
        for torrent in toberaised:
            if torrent.connection.maxrate[dir] > meanrate:
                allabovem.append(torrent)
            elif torrent.connection.maxrate[dir] < meanrate:
                raisedbelowm.append(torrent)
        for torrent in nottobechanged:
            if torrent.connection.maxrate[dir] > meanrate:
                allabovem.append(torrent)

        # -c-
        if raisedbelowm and allabovem:
            # Available bandwidth exchange :
            up = 0.0
            down = 0.0
            for torrent in raisedbelowm:
                toadd = meanrate - torrent.connection.maxrate[dir]

                maxlocalrate_float = float(torrent.connection.getLocalRate(dir))
                if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                    toadd = maxlocalrate_float - torrent.connection.maxrate[dir]
                up += toadd
            for torrent in allabovem:
                down += torrent.connection.maxrate[dir] - meanrate
            if up > down:
                limitup = down / up
            
            # Speed up slow torrents that want their rate to be raised :
            # Each one must have its reserved rate raised slowly enough to let it follow this raise if it really
            # wants to get higher. If we set the reserved to the max in one shot, these torrents will be then detected
            # in the next phase 1 as to be lowered, which is not what we want.
            realup = 0.0
            for torrent in raisedbelowm:
                maxup = torrent.connection.maxrate[dir]
                toadd = meanrate - maxup

                maxlocalrate_float = float(torrent.connection.getLocalRate(dir))
                if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                    toadd = maxlocalrate_float - maxup

                if up > down:
                    toadd *= limitup
                # step is computed such as if the torrent keeps on raising at the same rate as before, it will be
                # analysed as still wanting to raise by the next phase 1 check
                step = 2 * (torrent.connection.rate[dir] + self.calcupth2 - maxup)
                if toadd < step:
                    torrent.connection.maxrate[dir] = maxup + toadd
                    realup += toadd
                else:
                    torrent.connection.maxrate[dir] = maxup + step
                    realup += step
                #print "index :", torrent.listindex, "; rate raised from", maxup, "to", torrent.connection.maxrate[dir]          
            realup /= len(allabovem)
            # Slow down fast torrents :
            for torrent in allabovem:
                maxup = torrent.connection.maxrate[dir]
                torrent.connection.maxrate[dir] = maxup - realup
                #print "index :", torrent.listindex, "; rate lowered from", maxup, "to", torrent.listindex

        ################################################
        # Set new max rate to all active torrents
        ################################################
        for torrent in toberegulated:
            torrent.connection.setRate(torrent.connection.maxrate[dir], dir)
