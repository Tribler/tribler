import sys
from Tribler.simpledefs import UPLOAD
from Tribler.exceptions import NotYetImplementedException

DEBUG = True
class UploadLimitation:
    
    def __init__(self, session, ratemanager):
        self.session = session
        self.measure_interval = 5  # measure upload speed every 5 seconds
        self.register_get_download_states()
        
    def register_get_download_states(self):
        self.session.set_download_states_callback(self.upload_speed_callback)
        
    def download_states_callback(self, dslist):
        tota_upload = 0.0
        for downloadstate in dslist:
            upload = downloadstate.get_current_speed(UPLOAD)
            total_upload += upload
        self.upload_speed_callback(total_upload, dslist)
        return self.measure_interval
    
    def upload_speed_callback(self, speed, dslist):
        raise NotYetImplementedException()
    
    def set_max_upload_speed(self, speed, dslist):
        "Set the max_upload_speed in kb/s in the ratemanager and force speed adjust"
        self.ratemanager.set_global_max_speed(UPLOAD, speed)
        self.ratemanager.add_downloadstatelist(dslist)
        self.ratemanager.adjust_speeds()
        
    def log(self, s):
        if DEBUG:
            print >> sys.stderr, s
            
class TestUploadLimitation(UploadLimitation):
    def __init__(self, ratemanager, session):
        UploadLimitation.__init__(self, session, ratemanager)
        
    def upload_speed_callback(self, speed, dslist):
        self.log('Total ulspeed: %f' % speed)
        newspeed = max(0.0, speed-1.0)
        if newspeed == 0.0:
            newspeed = 50.0
        self.log('Setting max ulspeed to: %f' % newspeed)
        self.set_max_upload_speed(newspeed, dslist)