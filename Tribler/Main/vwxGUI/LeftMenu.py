
from wx import xrc
import wx, time, random
from safeguiupdate import FlaglessDelayedInvocation
#
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.TextButton import *
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.Dialogs.MugshotManager import MugshotManager
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles




DEBUG = False


class LeftMenu(wx.Panel,FlaglessDelayedInvocation):
    """
    Panel that shows one of the overview panels
    """
    def __init__(self, *args):
        
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
#        print 'standardOverview'
        self.triblerStyles = TriblerStyles.getInstance()
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        FlaglessDelayedInvocation.__init__(self)
        self.guiUtility = GUIUtility.getInstance()
        
        self.mainButtonClicked = None
        self.selectedMainButton = None
        self.activeH1 = None
        self.activeLeftBtn = None
        self.addComponents()

    def addComponents(self):
        # If you change the names here, 
        # please rename them also in the self.goToPage of this class

        self.SetBackgroundColour(self.triblerStyles.colours(1))
        self.menu = []
        self.menu.append(MenuItem(self,False, 'OVERVIEW'         , ['Start page', 
                                                                   'Stats']))        
        self.menu.append(MenuItem(self,False,'YOU'              , ['Profile']))
        self.menu.append(MenuItem(self,True, 'LIBRARY'          , ['All Downloads',
                                                                   'Highspeed',
                                                                   'Add playlist...']))
        self.menu.append(MenuItem(self,False, 'FRIENDS'          , ['All Friends']))
#        self.menu.append(MenuItem(self,True, 'FAV. CONTENT'     , ['All Favorites',
#                                                                   'Add favorites list...']))
        self.menu.append(MenuItem(self,False, 'FAV. USERS'       , ['All Subscriptions']))
        self.menu.append(MenuItem(self,False, 'GROUPS'           , ['Tribler 5',
                                                                   'Tribler 4',
                                                                   '< Tribler 4']))
#        self.menu.append(MenuItem(self,True, 'MESSAGES'         , ['Invitations', 
#                                                                   'Recommendations',
#                                                                   'Create folder...']))
#        self.menu.append(MenuItem(self,False,'SETTINGS'         , ['Notifications']))

        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        s=0
        for item in self.menu:
            item.addToSizer(self, self.vSizer, s) 
            s = s +1
            
        self.SetSizer(self.vSizer)
        self.SetAutoLayout(1)
        self.Layout()

        
    def buttonLeftClicked(self, event):   
        # remove addButton from previous active H1 
#        if self.activeH1:
#            self.activeH1.AddButtonIcon(False)
             
        obj = event.GetEventObject()
        self.goToPage(obj)        
        event.Skip()
            
    def goToPage(self, obj):
        
        name = obj.GetName()
        
        if not obj.isSelected():
            if self.selectedMainButton:
                self.selectedMainButton.setSelected(False)
            obj.setSelected(True)
            self.selectedMainButton = obj


        if name == 'Start page':
            self.guiUtility.standardStartpage()
        if name == 'Stats':
            self.guiUtility.standardStats()
#        elif name == 'All files':
#            self.guiUtility.standardFilesOverview()
        elif name == 'Tribler 4':
            self.guiUtility.standardPersonsOverview()
        elif name == 'Profile':
            self.guiUtility.standardProfileOverview()
        elif name == 'All Downloads':
            self.guiUtility.standardLibraryOverview()
        elif name == 'Highspeed':
            self.guiUtility.playlistOverview()
        elif name == 'All Friends':
            self.guiUtility.standardFriendsOverview()
        elif name == 'All Subscriptions':
            self.guiUtility.standardSubscriptionsOverview()
        elif name == 'Invitations':
            self.guiUtility.standardMessagesOverview()
        elif DEBUG:
            print >>sys.stderr,"GUIUtil: MainButtonClicked: unhandled name",name
        
class MenuItem:
    def __init__(self, parent, addItem, name, sublist = [] ):
        self.mm = MugshotManager.getInstance()
        self.parent = parent
        self.addItem = addItem
        self.name= name
        self.sublist = sublist   
        self.parent = parent
        self.buttons = []     
        self.buttons.append(TextButtonLeftH1(parent,name=self.name))        
        if self.addItem:
            for sub in sublist[:-1]:
               self.buttons.append(TextButtonLeft(parent, name=sub, icon=True))                
            self.buttons.append(TextButtonLeft(parent, self.addItem, name = sublist[-1], icon=True))
        else:
            for sub in sublist:
                self.buttons.append(TextButtonLeft(parent, name=sub, icon=True))
            
        self.enabled = True

        
    def addToSizer(self, parent, sizer, s):
        i = 0
        for button in self.buttons:
            if i == 0:                
                # the first Item is the H1 and is positioned differently
                if s == 0:
                    sizer.Add(button, 0, wx.EXPAND|wx.TOP, 0)
                else:
                    sizer.Add(button, 0, wx.EXPAND|wx.TOP, 15)
                button.Bind(wx.EVT_LEFT_UP, self.buttonLeftH1Clicked)
                i = 1
            else:
                sizer.Add(button, 0, wx.EXPAND|wx.TOP|wx.LEFT, 1)
                button.Bind(wx.EVT_LEFT_UP, self.buttonLeftClicked)
    
    def buttonLeftClicked(self, event):

        self.parent.buttonLeftClicked(event)
#        self.buttons[0].AddButtonIcon(True)
        
        
        obj = event.GetEventObject()
        
        if self.parent.activeLeftBtn != None:
            if self.parent.activeLeftBtn.addItem != True:
                print 'tb activeLeftBtn is ACTIVE'
                self.parent.activeLeftBtn.dropdown.Hide()
        
        self.parent.activeH1 = self.buttons[0]
        self.parent.activeLeftBtn = obj
        
        
        

#        print 'tb > self.GetName()= %s' % obj.GetName()
        
        if obj.addItem == True:

#            obj.SetBackgroundColour(wx.WHITE)
            obj.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            obj.text = wx.TextCtrl(obj, -1, style = wx.NO_BORDER|wx.TE_RICH|wx.TE_PROCESS_ENTER  )
    #        obj.text = TextEdit(obj,-1)
            obj.text.SetValue('Name')
            obj.text.SetFocus()
            obj.text.SetSelection(-1,-1)
            obj.text.Bind(wx.EVT_MOUSE_EVENTS, obj.mouseAction)            
            obj.text.Bind(wx.EVT_TEXT_ENTER, self.afterMenuItemAdded)
            obj.text.Bind(wx.EVT_KILL_FOCUS, self.afterMenuItemAdded)
            obj.hSizer.Add(obj.text, 1, wx.EXPAND|wx.LEFT, 12)
            
#            obj.newItem = ImagePanel(obj, -1, name='addNewItem')
#            obj.newItem.SetMinSize((16,16))
#            obj.hSizer.Add(obj.newItem, 0, wx.LEFT, 0)
        
        else:            
            obj.hSizer = wx.BoxSizer(wx.HORIZONTAL)  
            obj.dropdown = tribler_topButton(obj, -1, name='leftButtonOptions')
#            obj.download.SetMinSize((12,21))
            obj.dropdown.SetSize((12,21))                      
#            obj.dropdown = ImagePanel(obj, -1, wx.DefaultPosition, wx.Size(12,21),name='leftButtonOptions')
            obj.hSizer.Add([1,0], 1, wx.TOP, 0)
            obj.hSizer.Add(obj.dropdown, 0, wx.TOP|wx.EXPAND|wx.ALIGN_RIGHT, 0)
            obj.SetFocus()
            
#            obj.AddLeftButtonMenuIcon(True)
            
            
        obj.SetSizer(obj.hSizer)
        obj.SetAutoLayout(1)
        obj.Layout()
        obj.Refresh()

        event.Skip()
    
    def buttonLeftH1Clicked(self, event):
        self.enabled = not self.enabled # toggle enabled
        
        for button in self.buttons[1:]:
            button.Show(self.enabled)
            
        if self.enabled:
            self.buttons[0].Enabled(True)
        else:
            self.buttons[0].Enabled(False)
        
        self.parent.Layout()
        self.parent.Refresh()
        
    def afterMenuItemAdded(self, event):
        
        obj = event.GetEventObject()
#        obj.Unbind(wx.EVT_TEXT_ENTER, self.afterMenuItemAdded)
#        obj.Unbind(wx.EVT_KILL_FOCUS, self.afterMenuItemAdded)

        if obj.IsModified():
            
            newItem = TextButtonLeft(self.parent, name=obj.GetValue())
            newItem.Bind(wx.EVT_LEFT_UP, self.buttonLeftClicked)
            index = getSizerIndex(self.parent.vSizer, self.buttons[-1])
            self.buttons.insert(len(self.buttons)-1, newItem)
            self.sublist.insert(len(self.sublist)-1, obj.GetValue())
            
#            def callAfterfunction():
#                print 'tb > AFTER'
            self.parent.vSizer.Insert(index, newItem, 0, wx.TOP|wx.LEFT|wx.EXPAND, 1)
            self.parent.SetAutoLayout(1)
            self.parent.Layout()
            self.parent.Refresh()
                
#            wx.CallAfter(callAfterfunction)
        else:
            print 'tb > NOT Modified'
            
        obj.GetContainingSizer().Detach(obj)
        obj.Destroy()

        
def getSizerIndex(sizer, window):
    children = sizer.GetChildren()
    for i, child in enumerate(children):
        win = child.GetWindow()
        if win is window:
            return i
    return -1
        
        
        
        
        
    