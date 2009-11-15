READY_FOR_RELEASE = 1

if (READY_FOR_RELEASE == 0):
    import numpy
    import pylab

import time
from threading import *

import Status
import LivingLabReporter

class Plottable:
    def __init__(self, name, value = 0):
        self.name = name
        self.value = value
        self.valueLock = Lock()
        
    def getName(self):
        return self.name
    
    def setValue(self, value):
        self.valueLock.acquire()
        self.value = value
        self.valueLock.release()

    def getValue(self):
        self.valueLock.acquire()
        x = self.value
        self.valueLock.release()
        return x

class Plotter(Thread):
    def __init__(self, period, mypermid):
        Thread.__init__(self)
        self.period = period
        self.mypermid = mypermid

        self.stillRunning = 1
        self.stillRunningLock = Lock()
        self.registered = {}
        self.registeredLock = Lock()
        
        self.status = Status.get_status_holder("LivingLab")
        self.reporter = LivingLabReporter.LivingLabPeriodicReporter("Congestion Control Reporter", self.period, mypermid)
        self.status.add_reporter(self.reporter)

    def register(self, plottable):
        try:
            key = plottable.getName()
            if (key != None):
                try:
                    newElem = self.status.create_status_element(key, key)
                except:
                    newElem = self.status.get_status_element(key)
                newElem.set_value(0.0)
                self.registeredLock.acquire()
                self.registered[key] = (plottable, [], [], None, newElem)
                self.registeredLock.release() 
        except:
            pass

    def stopRunning(self):
        #print "Stopping Plotter"
        self.stillRunningLock.acquire()
        self.stillRunning = 0
        self.stillRunningLock.release()
        self.reporter.stop(True)

    def isRunning(self):
        self.stillRunningLock.acquire()
        x = self.stillRunning
        self.stillRunningLock.release()
        return x
        
    def run(self):                
        if (READY_FOR_RELEASE == 0):
            pylab.ion()
            self.fig = pylab.figure(1)
            self.subplot = pylab.subplot(111)
        self.tstart = time.time()

        sumxdata = []
        sumydata = []
        sumlines = None

        while (self.isRunning()):
            time.sleep(self.period)
            #print "New Plot"
            
            regList = []
            self.registeredLock.acquire()
            for plottableName in self.registered.keys():
                regList.append(self.registered[plottableName])
            self.registeredLock.release()

            tnow = time.time() - self.tstart
            legendNames = []
            xmin = None
            xmax = None
            ymin = None
            ymax = None
            sumy = 0
            
            for plottableTuple in regList:
                plottable, xdata, ydata, lines, elem = plottableTuple
                xdata.append(tnow)
                yvalue = plottable.getValue()
                sumy += yvalue
                ydata.append(yvalue)
                
                # for status reporting
                elem.set_value(yvalue)
                
                if (READY_FOR_RELEASE == 0):
                    if (lines == None):
                        lines = pylab.plot(xdata, ydata)
               
                    lines[0].set_data(xdata, ydata)
                    legendNames.append(plottable.getName())
                
                self.registeredLock.acquire()
                self.registered[plottable.getName()] = (plottable, xdata, ydata, lines, elem)
                self.registeredLock.release()

                cxmin = min(xdata)
                cxmax = max(xdata)
                cymin = min(ydata)
                cymax = max(ydata)
                
                if (xmin == None or cxmin < xmin):
                    xmin = cxmin
                if (xmax == None or cxmax > xmax):
                    xmax = cxmax
                if (ymin == None or cymin < ymin):
                    ymin = cymin
                if (ymax == None or cymax > ymax):
                    ymax = cymax
            
            sumxdata.append(tnow)
            sumydata.append(sumy)
            
            if (READY_FOR_RELEASE == 0):
                if (sumlines == None):
                    sumlines = pylab.plot(sumxdata, sumydata)
                sumlines[0].set_data(sumxdata, sumydata)
                legendNames.append("Sum")
            
                pylab.legend(legendNames)
            
            if (ymax == None or max(sumydata) > ymax):
                ymax = max(sumydata) 
            if (ymin == None or min(sumydata) < ymin):
                ymin = min(sumydata)

            if (READY_FOR_RELEASE == 0):
                if (xmin != None and xmax != None and ymax != None):
                    self.subplot.set_xlim(xmin, xmax)
                    self.subplot.set_ylim(0, 1.1 * ymax)
            
                pylab.draw()
        #print "Plotter stopped"
