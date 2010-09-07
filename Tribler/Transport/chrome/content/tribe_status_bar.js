
/*
  TribeStatuBar - functions for the SwarmPlayer status bar

  Written by Riccardo Petrocco
  see LICENSE.txt for license information
*/

// TODO make async requests using ajax

var TribeStatusBar = {
	// Install a timeout handler to install the interval routine

  startup: function()
  {
    this.refreshInformation();
    window.setInterval(this.refreshInformation, 1000);
    this.tribeChannel = null;
  },


  // Called periodically to refresh traffic information
  refreshInformation: function()
  {

    var httpRequest = null;
    var fullUrl = "http://127.0.0.1:6877/webUI?&{%22method%22:%22get_speed_info%22}";
    var tribeBar = this;

    function infoReceived()
    {

	    var tribePanel = document.getElementById('tribestatusbar');
	    var output = httpRequest.responseText;

		
	    if (output.length)
	    {
		    var resp = JSON.parse(output);

		    if(resp.success) {
		      
		      if (tribePanel.src != "chrome://tribe/skin/swarmplugin.png") {
    		    
		        tribePanel.src = "chrome://tribe/skin/swarmplugin.png";
  		        //tribePanel.onclick = openWebUI;
  		        tribePanel.onclick = openAndReuseTab;
    		    tribePanel.tooltipText="Click here to access the SwarmPlayer Web Interface"
    		  }
    		  
		      tribePanel.label = "Down: " + parseInt(resp.downspeed) + " KB/s, Up: " + parseInt(resp.upspeed) + " KB/s";
        }				
		

	    }

    }
    
    function openWebUI()
        {
          var win = Components.classes['@mozilla.org/appshell/window-mediator;1'].getService(Components.interfaces.nsIWindowMediator).getMostRecentWindow('navigator:browser'); 
          win.openUILinkIn('http://127.0.0.1:6877/webUI', 'tab');
        }
        
    function openAndReuseTab() 
        {
          url = "http://127.0.0.1:6877/webUI";
          var wm = Components.classes["@mozilla.org/appshell/window-mediator;1"]
                             .getService(Components.interfaces.nsIWindowMediator);
          var browserEnumerator = wm.getEnumerator("navigator:browser");

          // Check each browser instance for our URL
          var found = false;
          while (!found && browserEnumerator.hasMoreElements()) {
            var browserWin = browserEnumerator.getNext();
            var tabbrowser = browserWin.gBrowser;

            // Check each tab of this browser instance
            var numTabs = tabbrowser.browsers.length;
            for (var index = 0; index < numTabs; index++) {
              var currentBrowser = tabbrowser.getBrowserAtIndex(index);
              if (url == currentBrowser.currentURI.spec) {

                // The URL is already opened. Select this tab.
                tabbrowser.selectedTab = tabbrowser.tabContainer.childNodes[index];

                // Focus *this* browser-window
                browserWin.focus();

                found = true;
                break;
              }
            }
          }

          // Our URL isn't open. Open it now.
          if (!found) {
            var recentWindow = wm.getMostRecentWindow("navigator:browser");
            if (recentWindow) {
              // Use an existing browser window
              recentWindow.delayedOpenTab(url, null, null, null, null);
            }
            else {
              // No browser windows are open, so open a new one.
              window.open(url);
            }
          }
      }

    
    function restartBG()
    {

      TribeStatusBar.startBG();

    }
    
    function restoreBar()
    {
	    var tribePanel = document.getElementById('tribestatusbar');

      if (tribePanel.src != "chrome://tribe/skin/swarmplugin_grey.png") {    
          tribePanel.src = "chrome://tribe/skin/swarmplugin_grey.png";
	      tribePanel.onclick=restartBG;
	      tribePanel.label = " ";
		  tribePanel.tooltipText="SwarmPlayer: Sharing is disabled. Click here to start sharing"
		    
		  TribeStatusBar.tribeChannel = null;
      }
      
    }

    //TODO remove
    function reqTimeout()
    {
        httpRequest.abort();
        return;
        // Note that at this point you could try to send a notification to the
        // server that things failed, using the same xhr object.
    }
    
    try 
    {
        httpRequest = new XMLHttpRequest();
        httpRequest.open("GET", fullUrl, true);
        httpRequest.onload = infoReceived;
        httpRequest.onerror = restoreBar;
        httpRequest.send(null);
        // Timeout to abort in 5 seconds
        //var reqTimeout = setTimeout(reqTimeout(),1000);
        setTimeout(function()
            {
                httpRequest.abort();
                return;
            }
            ,1000);
    }
    catch( err )
    {
        aMsg = ("*** StatusBar : " + err.description);
        Cc["@mozilla.org/consoleservice;1"].getService(Ci.nsIConsoleService).logStringMessage(aMsg);
        dump(aMsg);
    }
  },
  
  startBG: function() {

    if (this.tribeChannel == null) { 
      var tribeChannel = Components.classes['@p2pnext.org/tribe/channel;1'].getService().wrappedJSObject;
                                       
      this.tribeChannel = tribeChannel;
                                       
    }
    
    if (!tribeChannel.init) {
      tribeChannel.startBackgroundDaemon();
    }
    
  },
  
}


window.addEventListener("load", function(e) { TribeStatusBar.startup(); }, false);
