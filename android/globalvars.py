import threading

global thumbnail_sem
thumbnail_sem = threading.BoundedSemaphore()
global app_ending
app_ending = False
global nfcCallback
nfcCallback = None
global skelly
skelly = None
global scanner
scanner = None
global videopref
videopref = "INTERNAL"
global torrentFolder
torrentFolder = None
global triblerfun
triblerfun = True
global videoFolder
videoFolder = None
