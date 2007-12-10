import sys
from Tribler.Core.simpledefs import UPLOAD
from Tribler.Core.exceptions import NotYetImplementedException

DEBUG = True
DUMMY = True
class UploadLimitation:
    
    def __init__(self, session, ratemanager):
        self.session = session
        self.logFilename = 'uploadLimitation.log'
        self.ratemanager = ratemanager
        self.measure_interval = 5  # measure upload speed every 5 seconds
        self.dslist = None
        self.register_get_download_states()
        
        
    def register_get_download_states(self):
        self.session.set_download_states_callback(self.download_states_callback)
        
    def download_states_callback(self, dslist):
        self.dslist = dslist
        total_upload = 0.0
        for downloadstate in dslist:
            upload = downloadstate.get_current_speed(UPLOAD)
            total_upload += upload
        self.log('Total ulspeed: %f' % total_upload)
        self.upload_speed_callback(total_upload)
        return (self.measure_interval, False)
    
    def upload_speed_callback(self, speed):
        raise NotYetImplementedException()
    
    def set_max_upload_speed(self, speed):
        "Set the max_upload_speed in kb/s in the ratemanager and force speed adjust"
        if DUMMY:
            self.log('Not setting max ulspeed to: %f (DUMMY MODE)' % speed)
            return
        
        self.log('Setting max ulspeed to: %f' % speed)
        self.ratemanager.set_global_max_speed(UPLOAD, speed)
        # also set upload limit for seeding
        self.ratemanager.set_global_max_seedupload_speed(speed)
        
        self.ratemanager.add_downloadstatelist(self.dslist)
        self.ratemanager.adjust_speeds()
        
    def log(self, s):
        if DEBUG:
            print >> sys.stderr, 'UploadLimitation: ', s
    
    def logSpeeds(self, speed, limit, mode):
        f = file(self.logFilename, 'a')
        f.write('%f\t%f\t%s\n' % (speed, limit, mode))
        f.close()
            
class TestUploadLimitation(UploadLimitation):
    """
    Test implementation of UploadLimitation.
    Decreases upload and sets 
    
    limit = current upload speed - 1
    
    When no uploadspeed anymore, set upload limit to 50 kb/s
    """
    def __init__(self, session, ratemanager):
        UploadLimitation.__init__(self, session, ratemanager)
        
    def upload_speed_callback(self, speed):
        newspeed = max(0.0, speed-1.0)
        if newspeed == 0.0:
            newspeed = 50.0
        
        self.set_max_upload_speed(newspeed)
        
class MeasureUploadLimitation(UploadLimitation):
    """
    """
    def __init__(self, session, ratemanager):
        
        self.minLimitTime = 3
        self.maxLimitTime = 80
        self.limitTime = 10
        self.measureTime = 4
        self.measureToLimitFactor = 0.95
        self.shortTermToLimitFactor = 0.7
        self.measureToGlobalMaxFactor = 0.9
        self.shortTermCorrectionFactor = 0.9
        self.shortTermLength = 4 # average this amount of measurements to get short term upload in limited mode
        self.step = 0
        self.uploadLimit = 0.0
        
        self.maxUpload = 0.0  # Max measured upload speed is stored here
        self.measureMode = True # start in measureMode
        self.freeMeasurements = []
        self.limitedMeasurements = []
        self.measureTimer = self.measureTime - 1
        self.limitTimer = self.limitTime - 1
        
        UploadLimitation.__init__(self, session, ratemanager)
        
    def upload_speed_callback(self, speed):
        self.logSpeeds(speed, self.uploadLimit, int(self.measureMode))
        self.maxUpload = max(self.maxUpload, speed)
        if self.measureMode:
            self.log('measure step %d/%d' % (self.measureTime - self.measureTimer,self.measureTime))
            self.measureModeUpdate(speed)
        else:
            self.log('limit step %d/%d' % (self.limitTime - self.limitTimer,self.limitTime))
            self.limitModeUpdate(speed)
        
        self.log('freeM: %s' % self.freeMeasurements)
        self.log('limitM: %s' % self.limitedMeasurements)
        
    def measureModeUpdate(self, speed):
        self.freeMeasurements.append(speed)
        if self.measureTimer == 0:
            # Switch to limit mode
            assert len(self.freeMeasurements) == self.measureTime
            measureMax = max(self.freeMeasurements)
            self.freeMeasurements = []
            # If measurement is similar to historic measurements, increase limit time
            if measureMax > self.measureToGlobalMaxFactor * self.maxUpload:
                self.limitTime = min(self.limitTime*2, self.maxLimitTime)
            else:
                self.limitTime = self.minLimitTime
            self.log('Changed limit time to: %d' % self.limitTime)
            
            self.measureMode = False
            self.limitTimer = self.limitTime - 1
            self.uploadLimit = self.measureToLimitFactor * measureMax
            self.log('Switching to limit mode with limit: %f' % self.uploadLimit)
            self.set_max_upload_speed(self.uploadLimit)            
            
        self.measureTimer -= 1
        
    def limitModeUpdate(self, speed):
        if self.limitTimer == 0:
            self.limitedMeasurements = []
            self.measureMode = True
            self.log('Switching to measure mode for %d steps' % self.measureTime)
            self.measureTimer = self.measureTime - 1
            self.uploadLimit = 0.0
            self.set_max_upload_speed(self.uploadLimit)
        else:
            self.limitedMeasurements.append(speed)
            shortTerm = self.getShortTermUpload()
            if (shortTerm is not None and 
                shortTerm < self.uploadLimit * self.shortTermToLimitFactor):
                self.log('Low shortTerm bw: %f to a limit of %f' % (shortTerm, self.uploadLimit))
                self.uploadLimit *= self.shortTermCorrectionFactor
                self.limitTime = self.minLimitTime
                self.limitTimer = min(self.limitTimer, self.limitTime-1)
                self.set_max_upload_speed(self.uploadLimit)
                self.log('Setting upload limit to %f and limittime to %d' % (self.uploadLimit, self.limitTime))
        self.limitTimer-= 1
    def getShortTermUpload(self):
        assert not self.measureMode
        if len(self.limitedMeasurements) >= self.shortTermLength:
            return sum(self.limitedMeasurements[-self.shortTermLength:]) / float(self.shortTermLength)
        else:
            return None
    
   
class PingUploadLimitation(UploadLimitation):
    """
    UploadLimitation based on ping delays.
    Keep a moving average of pings. If new pings are much slower than old ones, limit bandwidth
    """
    def __init__(self, session, ratemanager):
        UploadLimitation.__init__(self, session, ratemanager)
        
    def upload_speed_callback(self, speed):
        
    def ping(self):
        
          
        