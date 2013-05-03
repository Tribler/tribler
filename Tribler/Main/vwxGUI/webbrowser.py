import gtk
import webkit

class WebView:
    '''WebView is a class that allows you to browse the worldwideweb.'''
    
   
    def __init__(self):
        ''' Create the WebView.'''
        
        #Create the window.
        self.__window = gtk.Window()
        self.__window.resize(800,600)
        
        #Create vbox
        self.__vbox = gtk.VBox()
        
        '''Create all GUI elements for the top bar.'''
        #Create the top bar HBox.
        hbox = gtk.HBox()
        #Create all elements.
        self.__backButton = gtk.ToolButton(gtk.STOCK_GO_BACK)
        self.__backButton.connect("clicked", self.__goBack)
        
        self.__forwardButton = gtk.ToolButton(gtk.STOCK_GO_FORWARD)
        self.__forwardButton.connect("clicked", self.__goForward)
       
        refreshButton = gtk.ToolButton(gtk.STOCK_REFRESH)
        refreshButton.connect("clicked", self.__refresh)
        
        self.__urlBar = gtk.Entry()
        self.__urlBar.connect("activate", self.__onActive)
                      
        #Add all top bar elements.
        hbox.pack_start(self.__backButton, False)
        hbox.pack_start(self.__forwardButton, False)
        hbox.pack_start(refreshButton, False)
        hbox.pack_start(self.__urlBar)
        
        self.__vbox.pack_start(hbox, False)
        
        '''Create the browser'''
        #Create a scrollbars.
        self.__scroller = gtk.ScrolledWindow()
        
        #Create the webkit browser.
        self.__browser = webkit.WebView()
        self.__scroller.add(self.__browser)
        
        #Update the buttons and urlbar.
        self.__browser.connect("load_committed", self.__updateGUI)
        
        self.__vbox.pack_start(self.__scroller)
        self.__window.add(self.__vbox)
        #Show everything.
        self.__window.show_all()
        
    def __goBack(self, widget, data=None):
        '''Go backward in history'''
        self.__browser.go_back()
    
    def __goForward(self, widget, data=None):
        '''Go forward in history'''
        self.__browser.go_forward()
        
    def __refresh(self):
        '''Refresh the site'''
        self.__browser.reload()
        
    def __onActive(self, widge, data=None):
        '''Open the website. If http:// is forgotten, then it is added'''
        url = self.__urlBar.get_text()
        try:
            url.index("://")
        except:
            url = "http://"+url
        self.__urlBar.set_text(url)
        self.__browser.open(url)
    
    def __updateGUI(self, widget, data=None):
        '''Update the urlbar and buttons.'''
        self.__urlBar.set_text(widget.get_main_frame().get_uri())
        self.__backButton.set_sensitive(self.__browser.can_go_back())
        self.forwardButton.set_sensitive(self.__browser.can_go_forward()())
      
    def main(self):
        '''Start the window'''
        self.__browser.open("http://www.google.com")
        gtk.main()

webView = WebView()
webView.main()