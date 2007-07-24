import unittest
from Tribler.Dialogs.GUIServer import GUIServer
from time import sleep

class TestGUIServer(unittest.TestCase):
    
    def setUp(self):
        self.ntasks = 0
        self.completed = []
        self.guiserver = GUIServer()
        
    def tearDown(self):
        sleep(2)
        self.completed.sort()
        if self.completed != range(self.ntasks):
            print "test failed",self.completed
            self.assert_(False)
        self.guiserver.resetSingleton()

    def test_simple(self):
        self.ntasks = 1
        
        self.guiserver.register()
        self.guiserver.add_task(lambda:self.task(0),0)

    def test_more(self):
        self.ntasks = 10
        
        for i in range(self.ntasks):
            # lambda functions are evil, this is not the same as lambda:task(i)
            self.guiserver.add_task(self.define_task(i),0)
        self.guiserver.register()

    def define_task(self,num):
        return lambda:self.task(num)

    def task(self,num):
        print "Running task",num
        self.completed.append(num)
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestGUIServer))
    
    return suite
    
