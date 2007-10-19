import sys
import os
from time import time, clock

#from traceback import print_exc
#from cStringIO import StringIO

from Utility.constants import * #IGNORE:W0611
from Utility.helpers import union, difference
from safeguiupdate import DelayedEventHandler

################################################################
#
# Class: RateManger
#
# Keep the upload and download rates for torrents within
# the defined local and global limits. Adopted for Tribler API 
# by Arno Bakker
#
################################################################
class RateManager:
    def __init__(self,max_upload_rate,max_seed_upload_rate,max_download_rate)

        self.urm_enabled = True
        self.max_upload_rate = max_upload_rate 
        self.max_seed_upload_rate = max_seed_upload_rate
        self.max_download_rate = max_download_rate

        self.lock = RLock()
        
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

        self.timer = NamedTimer(4, self.RateTasks)


    def RateTasks(self):
        self.lock.acquire()
        
        # self.UploadRateMaximizer() TODO: add queueing system
        
        self.CalculateBandwidth("down")
        self.CalculateBandwidth("up")
        
        self.lock.release()
        self.timer = NamedTimer(4, self.RateTasks)


    def add_downloadstate(self,d,ds):
        #self.states.append(ds)
        self.statusmap[ds.get_status()].append((d,ds))
        stats = ds.get_stats()
        self.currentotal['up'] += stats['up']
        self.currentotal['down'] += stats['down']
            
    def clear_downloadstates(self):
        #self.states.clear()
        self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE] = []
        self.statusmap[DLSTATUS_WAITING4HASHCHECK] = []
        self.statusmap[DLSTATUS_HASHCHECKING] = []
        self.statusmap[DLSTATUS_DOWNLOADING] = []
        self.statusmap[DLSTATUS_SEEDING] = []
        self.statusmap[DLSTATUS_STOPPED] = []
        self.statusmap[DLSTATUS_STOPPED_ON_ERROR] = []
        self.currentotal = {}
        self.currentotal['up'] = 0.0
        self.currentotal['down'] = 0.0


    def MaxRate(self, dir = "up"):
        if dir == "up":
            if self.allseeds:
                # Static overall maximum up rate when seeding
                return self.max_seed_upload_rate
            else:
                # Static overall maximum up rate when downloading
                return self.max_upload_rate
        else:
            return self.max_download_rate
           
    # See if any torrents are in the "checking existing data"
    # or "allocating space" stages
    def any_torrents_checking(self):

        if len(self.statusmap[DLSTATUS_ALLOCATING_DISKSPACE]) > 0 or \
           len(self.statusmap[DLSTATUS_WAITING4HASHCHECK]) > 0 or \
           len(self.statusmap[DLSTATUS_HASHCHECKING]) > 0:
            return True
        return False


            
    def CalculateBandwidth(self, dir = "up"):
        if dir == "up":
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]+self.statusmap[DLSTATUS_SEEDING]
        else:
            workingset = self.statusmap[DLSTATUS_DOWNLOADING]

        # Limit working set to active torrents with connections:
        newws = []
        for ds in workingset:
            stats = ds.get_stats()
            statsobj = stats['stats']
            if statsobj.numSeeds+statsobj.numPeers > 0:
                newws.apppend(ds)
        workingset = newws

        # No active file, not need to calculate
        if not workingset:
            return
        
        maxrate = self.MaxRate(dir)
        # See if global rate settings are set to unlimited
        if maxrate == 0:
            # Unlimited rate
            for (d,ds) in workingset:
                if dir == "up":
                    # Arno: you have 2 values: the rate you want, and the rate you are allowed
                    # you want to remember the first too.
                    d.set_max_upload_rate(d.get_max_desired_upload_rate()) # TODO: optimize so less locking?
                else:
                    d.set_max_download_rate(d.get_max_desired_download_rate()) # TODO: optimize so less locking?
            return
        
        #print "====================== BEGINNING ALGO ======= th1=%.1f ; th2=%.1f =============================" % (self.calcupth1, self.calcupth2)

        #######################################################
        # - Find number of completed/incomplete torrent
        # - Number of torrent using local setting
        # - bandwidth already used by torrents
        # - Sorting of torrents in lists according to their will in matter
        #   of upload rate :
        #   (tobelowered, toberaisedinpriority, toberaised, nottobechanged)
        #######################################################

        # Option set in Preferences/Queue.
        # If not set, torrents with rate local settings are treated like other 
        # torrents, except they have their own max rate they can't cross over. 
        # The consequence is a behaviour slightly different from the behavior of
        # ABC releases prior to 2.7.0.
        # If set, this gives the algorithm the behaviour of ABC releases prior 
        # to 2.7.0 : the torrents with an rate local setting will be granted 
        # bandwidth in priority to fulfill their local setting, even is this one
        # is higher than the global max rate setting, and even if this bandwidth
        # must be taken from other active torrents without a local rate setting. 
        # These torrents will not take part in the rate exchange between active 
        # torrents when all bandwidth has been distributed, since they will have 
        # been served in priority.
        prioritizelocal = True # Arno set to True

        # torrents with local rate settings when prioritizelocal is set (see prioritizelocal)
        localprioactive = []       
    
        # torrents for which measured rate is lowering and so reserved rate can
        # be lowered
        tobelowered = []
     
        # torrents for which measured rate is growing and so reserved rate can 
        # be raised, (with reserved rate > 3 kB/s for uploading)
        toberaised  = []                           

        # torrents for which reserved rate can be raised, with reserved 
        # rate < 3 kB/s
        # These will always be raised even there's no available up bandwith, 
        # to fulfill the min 3 kB/s rate rule
        toberaisedinpriority = []                             

        # torrents for which reserved rate is not to be changed and 
        # is > rateminimum; (for these, the measured rate is between (max upload
        # reserved - calcupth1) and (max upload reserved - calcupth2)
        nottobechanged = []   

        # mean max rate for torrents to be raised or not to be changed ; it will
        # be used to decide which torrents must be raised amongst those that 
        # want to get higher and that must share the available up bandwidth. 
        # The torrents that don't want to change their rate and that are below 
        # 3 kB/s are not taken into account on purpose, because these ones will 
        # never be lowered to give more rate to a torrent that wants to raise 
        # its rate, or to compensate for the rate given to torrents to be raised
        # in priority.
        meanrate = 0.0            
        
        for (d,ds) in workingset:
            # Active Torrent
            torrent = (d,ds)
            (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)

            # Torrents dispatch
            if prioritizelocal and maxdesiredrate:
                localprioactive.append(torrent)
            elif currentrate < 0.05:
                # These are the torrents that don't want to have their rate 
                # changed and that have an allmost null rate. They will not go 
                # lower, we can reset their reserved rate until they want to get
                # higher.
                if dir == "up"
                    d.set_max_desired_upload_rate(0.0)
                else:
                    d.set_max_desired_download_rate(0.0)
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
            and (1 - (self.currenttotal[dir] / availableratetobedistributed) > 0.20)):
            #print "FREE WHEELING TORRENTS"
            # If there's still at least 20% of available bandwidth, let the 
            # torrents do want they want. Keep a reserved max rate updated not
            # to have to reinitilize it when we'll switch later from free
            # wheeling to controlled status. Give BitTornado the highest
            # possible value for max rate to speed up the rate rising.
            for (d,ds) in workingset:
                torrent = (d,ds)
                (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)

                newrate = currentrate + self.meancalcupth
                maxlocalrate = maxdesiredrate
                if maxlocalrate > 0:
                    rateToUse = maxlocalrate
                    if newrate > maxlocalrate:
                        newrate = maxlocalrate
                else:
                    rateToUse = self.MaxRate(dir)
                if dir == "up":
                    d.set_max_desired_upload_rate(newrate)
                    d.set_max_upload_rate(rateToUse)
                else:
                    d.set_max_desired_download_rate(newrate)
                    d.set_max_download_rate(rateToUse)
            return

        ###########################################################################
        # First treat special torrents before going on sharing and distributing
        ###########################################################################

        # Treat in priority the torrents with rate below 3 kB/s and that want to get a higher rate
        grantedfortoberaisedinpriority = 0.0
        for (d,ds) in toberaisedinpriority:
            torrent = (d,ds)
            (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
            
            newreservedrate = currentrate + self.meancalcupth
            if newreservedrate > self.rateminimum[dir]:
                grantedfortoberaisedinpriority += self.rateminimum[dir] - maxdesiredrate
                if dir == "up":
                    d.set_max_desired_upload_rate(self.rateminimum[dir])
                else:
                    d.set_max_desired_download_rate(self.rateminimum[dir])
            else:
                grantedfortoberaisedinpriority += newreservedrate - maxdesiredrate
                if dir == "up":
                    d.set_max_desired_upload_rate(newreservedrate)
                else:
                    d.set_max_desired_download_rate(newreservedrate)


        # Treat in priority the torrents with a local rate setting if "prioritize local" is set
        # As with the free wheeling torrents, keep on tracking the real value of rate while giving BitTornado
        # the highest max rate to speed up the rate rising.
        grantedforlocaltoberaised = 0.0
        for (d,ds) in localprioactive:
            torrent = (d,ds)
            (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
            
            newrate = currentrate + self.meancalcupth
            maxlocalrate = maxdesiredrate
            if newrate > maxlocalrate:
                newrate = maxlocalrate
            grantedforlocaltoberaised += newrate - maxdesiredrate

            if dir == "up":
                d.set_max_desired_upload_rate(newrate)
                d.set_max_upload_rate(maxlocalrate)
            else:
                d.set_max_desired_download_rate(newrate)
                d.set_max_download_rate(maxlocalrate)
            

        # Torrents that want to be lowered in rate (and give back some reserved bandwidth)
        givenbackbytobelowered = 0.0
        for (d,ds) in tobelowered:
            torrent = (d,ds)
            (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
            
            newreservedrate = currentrate + self.meancalcupth
            givenbackbytobelowered += newreservedrate - maxdesiredrate
            if dir == "up":
                d.set_max_desired_upload_rate(newreservedrate)
            else:
                d.set_max_desired_download_rate(newreservedrate)

        
        # Add to available rate to be distributed the rate given back by the torrents that have been lowered ;
        # Substract from available rate the rate used for each torrent that have been be raised in priority (torrents with rate
        # below 3 kB/s and that want to get higher).
        availableratetobedistributed += givenbackbytobelowered - grantedfortoberaisedinpriority - grantedforlocaltoberaised - self.currenttotal[dir]
        #print "availableratetobedistributed is %.3f" % availableratetobedistributed

        # localprioactive torrents have already been updated if prioritizelocal is set
        toberegulated = [torrent for torrent in workingset if torrent not in localprioactive]

        # There's nothing to do if no torrent want to be raised
        if not toberaised:
            ################################################
            # Set new max rate to all active torrents
            ################################################
            self.make_it_so(self,toberegulated)
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
            for (d,ds) in toberaised:
                torrent = (d,ds)
                (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
                
                maxup = maxdesiredrate
                newreservedrate = currentrate + self.meancalcupth
                toadd = newreservedrate

                maxlocalup = maxdesiredrate
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
            for (d,ds) in toberaised:
                torrent = (d,ds)
                (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
                
                maxup = maxdesiredrate
                newreservedrate = currentrate + self.meancalcupth
                newmaxup = maxup + (newreservedrate - maxup) * realupfactor

                maxlocalup = maxdesiredrate
                if maxlocalup > 0 and newreservedrate > maxlocalup:
                    newmaxup = maxup + (maxlocalup - maxup) * realupfactor

                if dir == "up":
                    d.set_max_desired_upload_rate(newmaxup)
                else:
                    d.set_max_desired_download_rate(newmaxup)
                #print "index :", torrent.listindex, "; rate raised from", maxup, "to", maxdesiredrate
            
            ################################################
            # Set new max rate to all active torrents
            ################################################
            self.make_it_so(self,toberegulated)
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
            
            rate_id = []
            for (d,ds)in pooltobelowered:
                torrent = (d,ds)
                currenrate = get_current_rate(d,ds,dir)
                if currentrate > self.rateminimum[dir]:
                    rate_id.append(torrent)

            sizerate_id = len(rate_id)
            # Sort by increasing reserved rate
            try:
                rate_id.sort(None, key = lambda x: x.connection.maxrate[dir])
            except:
                pass
            if rate_id:
                ratenotassignedforeach = availableratetobedistributed / sizerate_id
            # Compute new reserved rate
            i = 0
            for (d,ds) in rate_id:
                torrent = (d,ds)
                if dir == "up"
                    maxdesiredrate = d.get_max_desired_upload_rate()
                else:
                    maxdesiredrate = d.get_max_desired_download_rate()
                
                # (availableratetobedistributed and ratenotassignedforeach are negative numbers)
                newmaxrate = maxdesiredrate + ratenotassignedforeach
                i += 1
                if newmaxrate < self.rateminimum[dir]:
                    # if some rate lowering could not be dispatched, it will be distributed to the next torrents
                    # in the list (which are higher in max rate because the list is sorted this way)
                    if i != sizerate_id:
                        ratenotassignedforeach += (newmaxrate - self.rateminimum[dir]) / (sizerate_id - i)
                    newmaxrate = self.rateminimum[dir]
                if dir == "up":
                    d.set_max_desired_upload_rate(newmaxrate)
                else:
                    d.set_max_desired_download_rate(newmaxrate)

                
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
        
        for (d,ds) in toberaised:
            torrent = (d,ds)
            if dir == "up"
                maxdesiredrate = d.get_max_desired_upload_rate()
            else:
                maxdesiredrate = d.get_max_desired_download_rate()
            
            if maxdesiredrate > meanrate:
                allabovem.append(torrent)
            elif maxdesiredrate < meanrate:
                raisedbelowm.append(torrent)
        for (d,ds) in nottobechanged:
            torrent = (d,ds)
            if dir == "up"
                maxdesiredrate = d.get_max_desired_upload_rate()
            else:
                maxdesiredrate = d.get_max_desired_download_rate()
            
            if maxdesiredrate > meanrate:
                allabovem.append(torrent)

        # -c-
        if raisedbelowm and allabovem:
            # Available bandwidth exchange :
            up = 0.0
            down = 0.0
            for (d,ds) in raisedbelowm:
                torrent = (d,ds)
                if dir == "up"
                    maxdesiredrate = d.get_max_desired_upload_rate()
                else:
                    maxdesiredrate = d.get_max_desired_download_rate()
                
                toadd = meanrate - maxdesiredrate

                maxlocalrate_float = maxdesiredrate
                if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                    toadd = maxlocalrate_float - maxdesiredrate
                up += toadd
            for (d,ds) in allabovem:
                torrent= (d,ds)
                if dir == "up"
                    maxdesiredrate = d.get_max_desired_upload_rate()
                else:
                    maxdesiredrate = d.get_max_desired_download_rate()
                
                down += maxdesiredrate - meanrate
            if up > down:
                limitup = down / up
            
            # Speed up slow torrents that want their rate to be raised :
            # Each one must have its reserved rate raised slowly enough to let it follow this raise if it really
            # wants to get higher. If we set the reserved to the max in one shot, these torrents will be then detected
            # in the next phase 1 as to be lowered, which is not what we want.
            realup = 0.0
            for (d,ds) in raisedbelowm:
                torrent = (d,ds)
                (currentrate,currentlimit,maxdesiredrate) = get_rates(d,ds,dir)
                
                maxup = maxdesiredrate
                toadd = meanrate - maxup

                maxlocalrate_float = maxdesiredrate
                if maxlocalrate_float > 0 and maxlocalrate_float <= meanrate:
                    toadd = maxlocalrate_float - maxup

                if up > down:
                    toadd *= limitup
                # step is computed such as if the torrent keeps on raising at the same rate as before, it will be
                # analysed as still wanting to raise by the next phase 1 check
                step = 2 * (currentrate + self.calcupth2 - maxup)
                if toadd < step:
                    if dir == "up":
                        d.set_max_desired_upload_rate(maxup + toadd)
                    else:
                        d.set_max_desired_download_rate(maxup + toadd)
                    realup += toadd
                else:
                    if dir == "up":
                        d.set_max_desired_upload_rate(maxup + step)
                    else:
                        d.set_max_desired_download_rate(maxup + step)
                    realup += step
                #print "index :", torrent.listindex, "; rate raised from", maxup, "to", d.Xet_max_desired_Xrate[dir]          
            realup /= len(allabovem)
            # Slow down fast torrents :
            for (d,ds) in allabovem:
                if dir == "up"
                    maxdesiredrate = d.get_max_desired_upload_rate()
                    d.set_max_desired_upload_rate(maxdesiredrate - realup)
                else:
                    maxdesiredrate = d.get_max_desired_download_rate()
                    d.set_max_desired_download_rate(maxdesiredrate - realup)

                #print "index :", torrent.listindex, "; rate lowered from", maxup, "to", torrent.listindex

        ################################################
        # Set new max rate to all active torrents
        ################################################
        self.make_it_so(self,toberegulated)


    def make_it_so(self,torrentlist):
        for (d,ds) in torrentlist:
            if dir == "up":
                d.set_max_upload_rate(d.get_max_desired_upload_rate())
            else:
                d.set_max_download_rate(d.get_max_desired_download_rate())


def get_rates(d,ds,dir):
    stats = ds.get_stats()
    if dir == "up":
        currentrate = stats['up'] 
        currentlimit = d.get_max_upload_rate()
        maxdesiredrate = d.get_max_desired_upload_rate()
    else:
        currentrate = stats['down'] 
        currentlimit = d.get_max_download_rate()
        maxdesiredrate = d.get_max_desired_download_rate()
    return (currentrate,currentlimit,maxdesiredrate)

def get_current_rate(d,ds,dir):
    if dir == "up":
        currentrate = stats['up'] 
    else:
        currentrate = stats['down'] 
    return currentrate
