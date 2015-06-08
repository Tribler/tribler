import threading

global thumbnail_sem 
thumbnail_sem = threading.BoundedSemaphore()
global app_ending
app_ending = False
global nfcCallback
nfcCallback = None
