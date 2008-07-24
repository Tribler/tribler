# Fake VLC

PlayingStatus = 0
PauseStatus = 1
ForwardStatus = 2 
BackwardStatus = 3
InitStatus = 4
EndStatus = 5
UndefinedStatus = 6

class MediaControl:
   def __init__(self,params):
       pass

   def stop(self):
       pass

   def playlist_clear(self):
       pass
  
   def get_stream_information(self):
       d = {'status':InitStatus}
       return d

   def exit(self):
       pass
