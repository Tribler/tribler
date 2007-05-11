
import datetime

starttime = datetime.datetime.now()

def log(message):
    time = datetime.datetime.now() - starttime
    timestr = time.seconds * 1000 + time.microseconds / 1000 + time.days * 86400000
    timestr = "<%010d>" % timestr

    if type(message) == unicode:
        message = message.encode("utf-8")

    m = "Web2.0: " + timestr + " " + message
    print m
    
