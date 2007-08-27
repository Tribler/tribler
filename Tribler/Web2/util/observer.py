
import traceback
import threading
import copy

DEBUG = True

class Observer:

    def __init__(self):
        pass

    def update(self, subject, m):
        pass
    


class Subject:

    def __init__(self):
        self.__observers = []
        self.__lock = threading.RLock()
        self.__last = None
        self.__haslast = False


    def attach(self, observer):

        self.__lock.acquire()

        try:
            self.__observers.index[observer]
        except:
            self.__observers.append(observer)
            if self.__haslast:
                #update new observer with last message
                observer.update(self, self.__last)

        self.__lock.release()


    def detach(self, observer):

        self.__lock.acquire()

        try:
            self.__observers.remove(observer)
        except:
            pass

        self.__lock.release()


    def notify(self, m):

        self.__last = m
        self.__haslast = True

        self.__lock.acquire()

        # copy observers list
        # needed in case an observer
        # decides to detach in the update
        observers = copy.copy(self.__observers)

        for observer in observers:
            try:
                observer.update(self, m)
            except:
                if DEBUG:
                    print self                
                    traceback.print_exc()

        self.__lock.release()


